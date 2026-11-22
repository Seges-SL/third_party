f26_lab() (
  # Punto 5, ficha 26 (decisión 5, fila 2.9): la casilla AI Conversational de Usuarios MCP, guardada, ¿cambia el
  # grupo? En lab_pns_ai_cc0060e_14 (core cc0060e), con odoo-dev 14 shell --bd y el web parado. NADA SE ESCRIBE:
  # todo termina en rollback y se compara una huella tomada desde otro cursor de solo lectura.
  #   leer        versiones, grupos, AI Administrators, internos activos, seges_int y admin.
  #   REPRODUCIR  exige el último leer con TODO OK. En la transacción: admin pasa a AI Administrator (como en el
  #               staging) y seges_int recibe su fila de ai.mcp.user si no la tiene. Casos, cada uno en su savepoint,
  #               guardados por admin sin su: A1 solo la casilla (write), A2 solo la casilla (Form del formulario),
  #               B1 la casilla y AI Writer (write), B2 las dos (Form). Sin motor, lienzo ni skills.
  #   CREAR       (como REPRODUCIR; seges_int sin fila MCP) C1 create de la fila con la casilla (la interfaz no lo
  #               permite: create="0"); C2 el camino real: admin abre la lista (web_search_read con
  #               ensure_all_users crea la fila) y guarda la casilla con el Form.
  # Uso: bash ~/Descargas/f26_lab.sh leer | REPRODUCIR | CREAR
  set -u
  umask 077
  MODO=${1:-}
  TANDA="F26 LAB $MODO"
  DL=~/pns_ai_3973/informe
  LAB=~/GitHub/lab_pns_ai_cc0060e
  BD=lab_pns_ai_cc0060e_14
  ESTADO=~/odoo-dev/14.0/estado
  WEB=odoo-dev-14-web-1
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  ultima() { ls -t "$DL"/f26_lab-"$1"-*.txt 2>/dev/null | head -1; }
  marca() { if [ -n "$1" ] && [ -f "$1" ]; then grep -cx -- "$2" "$1" || true; else echo 0; fi; }
  FIN_L="Siguiente: bash ~/Descargas/f26_lab.sh REPRODUCIR"
  case "$MODO" in leer|REPRODUCIR|CREAR) ;; *) echo "Uso: bash $0 leer | REPRODUCIR | CREAR"; exit 1 ;; esac
  mkdir -p "$DL" && chmod 700 "$DL" || exit 1
  O="$DL/f26_lab-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA ($BD, todo con rollback): $(date '+%F %T')"
  if [ "$MODO" != leer ]; then
    UL=$(ultima leer)
    chk "último leer (${UL##*/}) con TODO OK" "$(marca "$UL" "== F26 LAB leer: TODO OK. $FIN_L")" 1
  fi
  chk "contexto activo lab_pns_ai_cc0060e" "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" "$LAB"
  chk "web parado" "$(docker ps --format '{{.Names}}' 2>/dev/null | grep -cx "$WEB" || true)" 0
  [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) antes del shell. No se ha seguido: pega la salida."; exit 1; }
  echo "== shell (odoo-dev 14 shell --bd $BD), a las $(date +%T)"
  SALIDA=$( { printf 'BD = "%s"\nMODO = "%s"\n' "$BD" "$MODO"; cat <<'PY'; } | (cd "$LAB" && odoo-dev 14 shell --bd "$BD") 2>&1
import logging
import odoo

VERSIONES = {'pns_base': '14.0.1.2.69', 'pns_ai_mcp': '14.0.3.1.973', 'pns_ai_chatboo': '14.0.2.1.587'}
GRUPOS = ('group_ai_admin', 'group_ai_writer', 'group_ai_external_url', 'group_ai_external_api',
          'group_ai_conversational')
CORTO = {'group_ai_admin': 'admin', 'group_ai_writer': 'writer', 'group_ai_external_url': 'url',
         'group_ai_external_api': 'api', 'group_ai_conversational': 'conv'}
SEGES_LOGIN = 'seges_int@example.com'
SEGES_ID = 8
ADMIN_ID = 2
VISTA = 'pns_ai_mcp.view_mcp_user_form'
fallos = []


def p(*a):
    print('F26 ' + ' '.join(str(x) for x in a))


def mal(texto):
    fallos.append(texto)
    p('FALLO', texto)


if env.cr.dbname != BD:
    print('F26 ERROR: la BD del shell no es ' + BD)
    raise SystemExit(1)


def huella():
    """Grupos de usuarios, filas de ai_mcp_user y write_date de res_users, desde otro cursor en solo lectura."""
    with odoo.registry(BD).cursor() as cr2:
        cr2.execute('SET TRANSACTION READ ONLY')
        cr2.execute("SELECT (SELECT count(*) FROM res_groups_users_rel),"
                    " (SELECT md5(coalesce(string_agg(gid || ':' || uid, ',' ORDER BY gid, uid), ''))"
                    "  FROM res_groups_users_rel),"
                    " (SELECT count(*) FROM ai_mcp_user),"
                    " (SELECT md5(coalesce(string_agg(concat_ws('|', id, user_id, write_date), ',' ORDER BY id), ''))"
                    "  FROM ai_mcp_user),"
                    " (SELECT md5(coalesce(string_agg(concat_ws('|', id, write_date), ',' ORDER BY id), ''))"
                    "  FROM res_users)")
        fila = tuple(cr2.fetchone())
        cr2.rollback()
    return fila


def en_grupo(uid, gid):
    env.cr.execute('SELECT count(*) FROM res_groups_users_rel WHERE uid = %s AND gid = %s', (uid, gid))
    return env.cr.fetchone()[0]


def fila_mcp(uid):
    env.cr.execute('SELECT id FROM ai_mcp_user WHERE user_id = %s', (uid,))
    r = env.cr.fetchone()
    return r[0] if r else None


def grupos_ia(uid):
    return ','.join(CORTO[x] for x in GRUPOS if en_grupo(uid, G[x].id)) or '-'


antes = huella()
p('huella antes: rel %d, mcp %d, %s/%s/%s' % (antes[0], antes[2], antes[1][:12], antes[3][:12], antes[4][:12]))

# 1. Versiones y grupos
mods = {m.name: (m.state, m.latest_version) for m in env['ir.module.module'].search([('name', 'in', list(VERSIONES))])}
for n, v in sorted(VERSIONES.items()):
    got = mods.get(n, ('falta', None))
    p('módulo %s: %s %s' % (n, got[0], got[1]))
    if got != ('installed', v):
        mal('módulo %s: esperado installed %s' % (n, v))
G = {}
for x in GRUPOS:
    G[x] = env.ref('pns_ai_mcp.' + x, raise_if_not_found=False)
    if not G[x]:
        mal('falta el grupo ' + x)
if fallos:
    env.cr.rollback()
    p('VEREDICTO ' + MODO.upper() + ' FALLO')
    raise SystemExit(1)
implica = G['group_ai_conversational'] in G['group_ai_admin'].implied_ids
p('AI Administrator implica AI Conversational: %s' % ('sí' if implica else 'no'))
if not implica:
    mal('AI Administrator no implica AI Conversational')

# 2. Usuarios
U = env['res.users'].with_context(active_test=False)
admins = U.search([('active', '=', True), ('groups_id', 'in', G['group_ai_admin'].id)])
p('AI Administrators activos: %d' % len(admins))
if len(admins) != 0:
    mal('hay AI Administrators en la BD (esperado 0)')
for u in U.search([('active', '=', True), ('share', '=', False)], order='id'):
    p('interno %d %s: IA %s; fila MCP %s' % (u.id, u.login, grupos_ia(u.id), 'sí' if fila_mcp(u.id) else 'no'))
seges = U.search([('login', '=', SEGES_LOGIN)])
admin = U.browse(ADMIN_ID).exists()
if len(seges) != 1 or seges.id != SEGES_ID or not seges.active or seges.share:
    mal('seges_int: esperado id %d, activo e interno' % SEGES_ID)
elif grupos_ia(SEGES_ID) != '-':
    mal('seges_int ya tiene grupos IA')
if not admin or admin.login != 'admin' or not en_grupo(ADMIN_ID, env.ref('base.group_system').id):
    mal('admin (id 2) con Ajustes')
elif en_grupo(ADMIN_ID, G['group_ai_admin'].id):
    mal('admin ya es AI Administrator')

resultados = []
if MODO in ('REPRODUCIR', 'CREAR') and not fallos:
    from odoo.tests.common import Form

    cuenta = {'añadido': 0}

    class Contador(logging.Handler):
        def emit(self, record):
            if 'added to group' in record.getMessage():
                cuenta['añadido'] += 1

    lg = logging.getLogger('odoo.addons.pns_ai_mcp.models.mcp_user')
    h = Contador(level=logging.INFO)
    nivel = lg.level
    lg.addHandler(h)
    lg.setLevel(logging.INFO)

    # Preparación, como superusuario y dentro de la transacción
    admin.write({'groups_id': [(4, G['group_ai_admin'].id)]})
    env['res.users'].flush()
    p('preparación: admin con AI Administrator: %s; con AI Conversational por la implicación: %s'
      % (en_grupo(ADMIN_ID, G['group_ai_admin'].id), en_grupo(ADMIN_ID, G['group_ai_conversational'].id)))
    rid = fila_mcp(SEGES_ID)
    if MODO == 'REPRODUCIR':
        if not rid:
            env['ai.mcp.user'].with_context(mcp_skip_ensure_all_users=True).create({'user_id': SEGES_ID})
            env['ai.mcp.user'].flush()
            rid = fila_mcp(SEGES_ID)
            p('preparación: fila de ai.mcp.user de seges_int creada en la transacción (id %s)' % rid)
        else:
            p('preparación: seges_int ya tenía fila de ai.mcp.user (id %s)' % rid)
    elif rid:
        mal('CREAR necesita a seges_int sin fila de ai.mcp.user (tiene la %s)' % rid)
    else:
        p('preparación: seges_int sin fila de ai.mcp.user (la crea cada caso)')
    env.clear()
    ea = env(user=ADMIN_ID, su=False)
    p('actor: uid %d, su %s, AI Administrator %s' % (ea.uid, ea.su, en_grupo(ea.uid, G['group_ai_admin'].id)))

    def filas_mcp():
        env.cr.execute('SELECT count(*) FROM ai_mcp_user')
        return env.cr.fetchone()[0]

    def con_form(rec, vals):
        f = Form(rec, view=VISTA)
        for k, v in vals.items():
            setattr(f, k, v)
        f.save()
        return ','.join('%s=%s' % (k[6:], getattr(f, k)) for k in vals)

    def a_write(vals):
        rec = ea['ai.mcp.user'].browse(rid)
        previo = {k: rec[k] for k in vals}
        rec.write(dict(vals))
        return previo, '-', ''

    def a_form(vals):
        rec = ea['ai.mcp.user'].browse(rid)
        previo = {k: rec[k] for k in vals}
        return previo, con_form(rec, vals), ''

    def c_create(vals):
        n0 = filas_mcp()
        ea['ai.mcp.user'].create(dict(vals, user_id=SEGES_ID))
        ea['ai.mcp.user'].flush()
        return {k: '(nueva)' for k in vals}, '-', 'filas creadas %d' % (filas_mcp() - n0)

    def c_lista_form(vals):
        n0 = filas_mcp()
        ea['ai.mcp.user'].with_context(ensure_all_users=True).web_search_read(
            [], fields=['name', 'login', 'is_ai_conversational'])
        ea['ai.mcp.user'].flush()
        nueva = fila_mcp(SEGES_ID)
        n1 = filas_mcp()
        env.clear()
        if not nueva:
            raise LookupError('la lista no creó la fila de seges_int')
        rec = ea['ai.mcp.user'].browse(nueva)
        previo = {k: rec[k] for k in vals}
        return previo, con_form(rec, vals), 'filas creadas al abrir la lista %d' % (n1 - n0)

    if MODO == 'REPRODUCIR':
        CASOS = (
            ('A1', 'write', a_write, {'is_ai_conversational': True}),
            ('A2', 'Form', a_form, {'is_ai_conversational': True}),
            ('B1', 'write', a_write, {'is_ai_conversational': True, 'is_ai_writer': True}),
            ('B2', 'Form', a_form, {'is_ai_conversational': True, 'is_ai_writer': True}),
        )
    else:
        CASOS = (
            ('C1', 'create', c_create, {'is_ai_conversational': True}),
            ('C2', 'lista y Form', c_lista_form, {'is_ai_conversational': True}),
        )
    for caso, via, accion, vals in (CASOS if not fallos else ()):
        env.cr.execute('SAVEPOINT f26_caso')
        env.clear()
        cuenta['añadido'] = 0
        error = None
        try:
            previo, mostrado, nota = accion(vals)
            ea['ai.mcp.user'].flush()
        except Exception as e:
            error = type(e).__name__
        if error:
            p('%s (%s): ERROR %s' % (caso, via, error))
            resultados.append('%s ERROR' % caso)
        else:
            env.clear()
            fila = fila_mcp(SEGES_ID)
            rec2 = ea['ai.mcp.user'].browse(fila)
            releida = ','.join('%s=%s' % (k[6:], rec2[k]) for k in vals) if fila else 'sin fila'
            sql = ','.join('%s=%d' % (k[6:], en_grupo(SEGES_ID, G['group_' + k[3:]].id)) for k in vals)
            u8 = ea['res.users'].browse(SEGES_ID)
            orm = ','.join('%s=%s' % (k[6:], G['group_' + k[3:]] in u8.groups_id) for k in vals)
            conv = en_grupo(SEGES_ID, G['group_ai_conversational'].id)
            veredicto = 'NO REPRODUCIDO (el grupo cambió)' if conv else 'REPRODUCIDO (el grupo no cambió)'
            p('%s (%s): %santes %s; formulario tras guardar %s; releída %s; grupo SQL %s; groups_id %s; '
              'log «added to group» %d; %s'
              % (caso, via, (nota + '; ') if nota else '', ','.join('%s=%s' % (k[6:], v) for k, v in previo.items()),
                 mostrado, releida, sql, orm, cuenta['añadido'], veredicto))
            resultados.append('%s %s' % (caso, 'NO_REPRODUCIDO' if conv else 'REPRODUCIDO'))
        env.cr.execute('ROLLBACK TO SAVEPOINT f26_caso')
        env.clear()
    lg.removeHandler(h)
    lg.setLevel(nivel)

env.cr.rollback()
env.clear()
despues = huella()
igual = despues == antes
p('huella después del rollback: %s' % ('igual' if igual else 'CAMBIÓ'))
if not igual:
    mal('la huella cambió')
if MODO in ('REPRODUCIR', 'CREAR'):
    p('RESULTADOS ' + ' '.join(resultados))
p('VEREDICTO %s %s' % (MODO.upper(), 'OK' if not fallos else 'FALLO'))
PY
)
  printf '%s\n' "$SALIDA" | grep '^F26 ' || echo "Sin líneas «F26»: el shell no ejecutó el script."
  V=$(printf '%s\n' "$SALIDA" | grep -c "^F26 VEREDICTO $(printf '%s' "$MODO" | tr a-z A-Z) OK\$" || true)
  if [ "$V" != 1 ]; then
    printf '%s\n' "$SALIDA" | grep -q '^F26 VEREDICTO ' || echo "El shell no terminó. Errores, solo el tipo: $(printf '%s\n' "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
    F=$((F + 1))
  fi
  chk "web parado al acabar" "$(docker ps --format '{{.Names}}' 2>/dev/null | grep -cx "$WEB" || true)" 0
  if [ "$F" = 0 ]; then
    if [ "$MODO" = leer ]; then echo "== $TANDA: TODO OK. $FIN_L"
    else echo "== $TANDA: TODO OK. Nada escrito (rollback, huella igual). Pega la salida."; fi
  else echo "== $TANDA: $F FALLO(S). Pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
f26_lab "$@"
