#!/usr/bin/env bash
# Pruebas con toda la rama: planta P-11 y P-14 en una BD con 3.1.879 recién
# instalada (lab_p2a_879_14 o lab_p2b_879_14, D42), antes del -u.
#   P-11 (§6.2 de comparacion_pns_ai_3-1-973.md): usuario seges_p11_admin con
#        AI Administrator y SIN AI Conversational (en 3.1.879 AI Administrator
#        no implica AI Conversational: modulos_3879/pns_ai_mcp/security/
#        security_groups.xml:50).
#   P-14 (skills retiradas, §7.3): sesión de Chatboo con cash_forecast activa
#        (active_skill_code y active_skill_params, modulos_3879/pns_ai_chatboo/
#        models/chatboo_session.py:132-146) y una fila de su caché de parámetros
#        (ai.skill.param.cache, skill_id en cascada: modulos_3879/pns_ai_mcp/
#        models/ai_skill_param_cache.py:31-62).
#
# Antes, una FOTO de solo lectura (sin commit): versiones de los tres módulos,
# grupos de los AI Administrators, code de los dos crons de NUEVO-2, las siete
# skills retiradas con su caché y lo ya plantado. Comprueba que la BD tiene
# 3.1.879 instalado y que el código montado también lo es (versiones de los
# manifests de ~/pns_ai_3973/fase0/modulos_3879: pns_base/__manifest__.py:8
# '1.2.47', pns_ai_mcp/__manifest__.py:8 '3.1.879' y pns_ai_chatboo/
# __manifest__.py:7 '2.1.538'; en la BD, con el prefijo 14.0.).
#
# ESCRIBE en la BD indicada (tras «s/N»): crea el usuario y la sesión y la fila
# de la caché, y hace commit. No toca nada más.
#
# Uso: bash rama_plantar.sh --bd lab_p2a_879_14|lab_p2b_879_14
#      (contexto de odoo-dev 14: lab_pns_ai_879; contenedor web parado)
# Códigos: 0 plantado; 1 no se plantó (nada escrito) o la foto falló;
# 10 respuesta distinta de «s»; 11 web en marcha o docker no responde;
# 12 argumentos no válidos; 13 falta la carpeta del laboratorio; 14 el contexto
# activo no es lab_pns_ai_879; 15 la BD no tiene 3.1.879 (o el código montado no
# lo es) o ya hay algo plantado.
set -uo pipefail

LAB_NOMBRE=lab_pns_ai_879
LAB=~/GitHub/$LAB_NOMBRE
ESTADO=~/odoo-dev/14.0/estado
BD=
while [ $# -gt 0 ]; do
    case "$1" in
        --bd) [ $# -ge 2 ] || { echo "Falta el valor de --bd."; exit 12; }; BD=$2; shift 2 ;;
        *) echo "Argumento no válido: $1"; exit 12 ;;
    esac
done
case "$BD" in
    lab_p2a_879_14|lab_p2b_879_14) ;;
    *) echo "Uso: rama_plantar.sh --bd lab_p2a_879_14|lab_p2b_879_14"; exit 12 ;;
esac
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
[ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "El contexto activo de odoo-dev 14 no es $LAB_NOMBRE (ver $ESTADO): no se hace nada."; exit 14; }
NOMBRES=$(docker ps --format '{{.Names}}' 2>/dev/null) || { echo "«docker ps» no responde."; exit 11; }
if printf '%s\n' "$NOMBRES" | grep -qx 'odoo-dev-14-web-1'; then
    echo "El contenedor odoo-dev-14-web-1 está en marcha: primero «Al acabar» y «odoo-dev 14 parar»."; exit 11
fi

COMUN=$(cat <<'PY'
import json
from odoo.modules.module import load_information_from_description_file

VERSIONES = {'pns_base': '14.0.1.2.47', 'pns_ai_mcp': '14.0.3.1.879', 'pns_ai_chatboo': '14.0.2.1.538'}
CRONS = ('pns_ai_mcp.ir_cron_ai_fetch_cache_gc', 'pns_ai_mcp.ir_cron_ai_api_result_cache_gc')
RETIRADAS = ('annual_billing', 'cash_forecast', 'credit_facility', 'customer_risk_analysis',
             'sys_info', 'users_all', 'users_logged')
LOGIN_P11 = 'seges_p11_admin'
SESION_P14 = 'Seges P-14 cash_forecast activa'
FRASE_P14 = 'seges p14 ocho semanas'
PARAMS_P14 = {'weeks': 8}


def fallo(motivo, codigo=1):
    # Sin commit: no queda nada escrito.
    print('RAMA ERROR: ' + motivo)
    raise SystemExit(codigo)


if env.cr.dbname != BD:
    fallo('la BD del shell no es ' + BD)
mods = env['ir.module.module'].sudo().search([('name', 'in', list(VERSIONES))])
bd_ok = codigo_ok = len(mods) == 3
for m in mods:
    codigo_v = (load_information_from_description_file(m.name) or {}).get('version')
    print('RAMA versión %s: BD %s (%s), código montado %s' % (m.name, m.latest_version, m.state, codigo_v))
    bd_ok = bd_ok and m.state == 'installed' and m.latest_version == VERSIONES[m.name]
    codigo_ok = codigo_ok and codigo_v == VERSIONES[m.name]
admin_g = env.ref('pns_ai_mcp.group_ai_admin')
conv_g = env.ref('pns_ai_mcp.group_ai_conversational')
admins = admin_g.with_context(active_test=False).users
print('RAMA AI Administrators: %d (ids %s); con AI Conversational: %d' % (
    len(admins), sorted(admins.ids), len(admins & conv_g.users)))
for x in CRONS:
    cron = env.ref(x, raise_if_not_found=False)
    print('RAMA cron %s: %s' % (x, json.dumps((cron.code or '').strip()) if cron else 'NO EXISTE'))
Skill = env['ai.skill'].sudo().with_context(active_test=False)
Cache = env['ai.skill.param.cache'].sudo().with_context(active_test=False)
for code in RETIRADAS:
    s = Skill.search([('code', '=', code)])
    print('RAMA skill %s: filas %d, de fábrica (pns_ai_chatboo, sin dueño) %d, caché %d' % (
        code, len(s), len(s.filtered(lambda r: r.source_module == 'pns_ai_chatboo' and not r.owner_id)),
        Cache.search_count([('skill_id', 'in', s.ids)])))
Users = env['res.users'].sudo().with_context(active_test=False)
Sesiones = env['chatboo.session'].sudo().with_context(active_test=False)
ya = (Users.search_count([('login', '=', LOGIN_P11)]), Sesiones.search_count([('name', '=', SESION_P14)]),
      Cache.search_count([('unresolved', '=', FRASE_P14)]))
print('RAMA ya plantado: usuario %d, sesión %d, caché %d' % ya)
if not bd_ok:
    fallo('la BD no tiene los tres módulos instalados en 3.1.879', 15)
if not codigo_ok:
    fallo('el código montado no es 3.1.879 (¿contexto equivocado?)', 15)
if any(ya):
    fallo('ya hay algo plantado: se revisa a mano', 15)
PY
)

# 1. Foto (solo lectura; el shell hace rollback al salir).
FOTO=$({ printf 'BD = "%s"\n' "$BD"; echo "$COMUN"; echo "print('RAMA FOTO OK')"; } | odoo-dev 14 shell --bd "$BD" 2>&1)
echo "$FOTO" | grep '^RAMA ' || echo "Sin líneas «RAMA»: el shell no ejecutó el script."
if ! echo "$FOTO" | grep -qx 'RAMA FOTO OK'; then
    echo "$FOTO" | grep -q 'RAMA ERROR: .*\(3.1.879\|plantado\)' && exit 15
    echo "Foto fallida (nada escrito). Errores del shell, solo el tipo: $(echo "$FOTO" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
    exit 1
fi

read -rp "Esto ESCRIBE en $BD: crea el usuario seges_p11_admin (P-11) y la sesión y la caché de P-14. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se planta."; exit 10; }

# 2. Plantar (repite las comprobaciones de la foto y hace commit).
SALIDA=$({ printf 'BD = "%s"\n' "$BD"; echo "$COMUN"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" 2>&1
user_g = env.ref('base.group_user')
usuario = Users.with_context(no_reset_password=True).create({
    'name': 'Seges P-11 admin',
    'login': LOGIN_P11,
    'groups_id': [(6, 0, [user_g.id, admin_g.id])],
})
if not usuario.has_group('pns_ai_mcp.group_ai_admin') or usuario.has_group('pns_ai_mcp.group_ai_conversational'):
    fallo('seges_p11_admin no queda con AI Administrator y sin AI Conversational')
skill = Skill.search([('code', '=', 'cash_forecast'), ('source_module', '=', 'pns_ai_chatboo'),
                      ('owner_id', '=', False)])
if len(skill) != 1:
    fallo('no hay una sola skill cash_forecast de fábrica (hay %d)' % len(skill))
sesion = Sesiones.create({
    'name': SESION_P14,
    'user_id': env.ref('base.user_admin').id,
    'active_skill_code': 'cash_forecast',
    'active_skill_params': json.dumps(PARAMS_P14),
})
cache = Cache.create({
    'skill_id': skill.id,
    'unresolved': FRASE_P14,
    'params_json': json.dumps(PARAMS_P14, sort_keys=True),
})
env.cr.commit()
print('RAMA PLANTADO usuario=%d sesion=%d skill=%d cache=%d' % (usuario.id, sesion.id, skill.id, cache.id))
PY
)
echo "$SALIDA" | grep '^RAMA \(ERROR\|PLANTADO\)' || echo "Sin línea «RAMA»: el shell no ejecutó el script."
echo "$SALIDA" | grep -q '^RAMA PLANTADO ' && exit 0
echo "No se plantó (nada escrito). Errores del shell, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
exit 1
