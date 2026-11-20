#!/usr/bin/env python3
"""Prueba 4 bis de E2′ (P-82, parche 11 adaptado): borrado en cascada con un adjunto ajeno enganchado.

Sustituye, para esta prueba, a preparar_e2.py y prueba4_bis_e2.py de la E2 de la 3.1.782: no crea ni
toca e2_aiadmin (archivado en pns_demo) ni ningún otro usuario fuera de LOGINS, y no usa
e2_estado.json.

  python3 prueba4_bis_e2p.py --preparar   crea (o reactiva) A2 y B, internos sin más grupos, y el
                                          adjunto huérfano X de A2; guarda los ids en e2p_estado.json
  python3 prueba4_bis_e2p.py              la 4 bis:
        1  B crea su sesión CS_B2
        2  (pausa, [ALTERA]) Sergio engancha X a CS_B2 por SQL; el script comprueba el enganche
        3  B crea Z2, adjunto propio colgado de CS_B2, y borra CS_B2 con unlink (el método al que
           llama el borrado de History: /chatboo/sessions/delete -> session.unlink())
        4  Z2 borrado; CS_B2 borrada; X existe con res_model vacío, res_id 0 y create_uid de A2;
           A2 descarga X (200) y B no (404)
  python3 prueba4_bis_e2p.py --limpiar    cada usuario borra sus sesiones; se borran X y Z2 y los dos
                                          usuarios con sus contactos (si no se puede, se archivan)

Biblioteca estándar. Contraseñas del entorno (no se guardan ni se imprimen):
  E2P_URL (http://localhost:8169), E2P_DB (lab_pns_ai_3879_14), E2P_ADM_LOGIN (admin), E2P_ADM_PASS,
  E2P_TEST_PASS (contraseña común de A2 y B), E2P_PSQL (comando psql para la pausa; por defecto el del
  staging en el VPS, con la BD de E2P_DB).
"""
import datetime
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get('E2P_URL', 'http://localhost:8169').rstrip('/')
DB = os.environ.get('E2P_DB', 'lab_pns_ai_3879_14')
PSQL = os.environ.get('E2P_PSQL') or (
    "docker exec -i odoo14_pns_db sh -c 'psql -U \"$POSTGRES_USER\" -d %s'" % DB)
ESTADO = 'e2p_estado.json'
LOGINS = {  # los únicos usuarios que este script crea, modifica o borra
    'A2': ('e2p_interno_a', 'E2P interno A (pruebas)'),
    'B': ('e2p_interno_b', 'E2P interno B (pruebas)'),
}
assert all(login.startswith('e2p_') for login, _n in LOGINS.values())
# Si un usuario e2p_* ya existe con alguno de estos grupos, no es nuestro: no se toca.
FORBIDDEN = ('base.group_system', 'base.group_erp_manager',
             'pns_ai_mcp.group_ai_admin', 'pns_ai_mcp.group_ai_conversational')
fallos = 0


class RpcError(Exception):
    def __init__(self, msg, name=None):
        super().__init__(msg)
        self.name = name or ''


class Session:
    def __init__(self, login, pwd):
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        res = self.post('/web/session/authenticate', {'db': DB, 'login': login, 'password': pwd})
        if not (res or {}).get('uid'):
            raise RpcError('no se pudo iniciar sesión como %s' % login)
        self.uid = res['uid']

    def post(self, path, params):
        body = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': params}).encode()
        req = urllib.request.Request(URL + path, data=body,
                                     headers={'Content-Type': 'application/json'})
        with self.op.open(req, timeout=60) as resp:
            res = json.loads(resp.read().decode())
        if 'error' in res:
            data = res['error'].get('data') or {}
            raise RpcError('%s: %s' % (data.get('name'), data.get('message') or res['error'].get('message')),
                           data.get('name'))
        return res.get('result')

    def kw(self, model, method, args, kwargs=None):
        return self.post('/web/dataset/call_kw/%s/%s' % (model, method),
                         {'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {}})

    def get(self, path):
        try:
            with self.op.open(URL + path, timeout=60) as resp:
                resp.read()
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code


def login_or_exit(login, pwd):
    try:
        return Session(login, pwd)
    except RpcError as exc:
        sys.exit('ERROR: %s' % exc)


def load_state():
    if not os.path.exists(ESTADO):
        sys.exit('No existe %s: ejecuta antes --preparar.' % ESTADO)
    with open(ESTADO) as fh:
        return json.load(fh)


def save_state(estado):
    with open(ESTADO, 'w') as fh:
        json.dump(estado, fh, indent=1)


def user_id(adm, login):
    ids = adm.kw('res.users', 'search', [[('login', '=', login), ('active', 'in', [True, False])]])
    return ids[0] if ids else None


def check(what, ok, got, exp):
    global fallos
    fallos += 0 if ok else 1
    print('4b  %-56s %-30s %s' % (what[:56], str(got)[:30], 'OK' if ok else 'INESPERADO (%s)' % (exp,)))


def att(ses, i):
    """(res_model, res_id, create_uid) de un adjunto; None si no existe; 'sin acceso' si ses no lo ve.

    Con read y no con search_read: en Odoo 14, ir.attachment._search oculta los adjuntos enganchados
    a un registro que el usuario no puede leer (una sesión de chat ajena, también para admin) y los
    enganchados a un registro que ya no existe. Con search_read, un Z2 que sobreviviera colgado de la
    sesión borrada parecería borrado. read, en cambio, da MissingError si el adjunto no existe, lo
    devuelve si cuelga de un registro inexistente y da AccessError si cuelga de uno ajeno."""
    try:
        r = ses.kw('ir.attachment', 'read', [[i], ['res_model', 'res_id', 'create_uid']])
    except RpcError as exc:
        if exc.name.endswith('MissingError'):
            return None
        if exc.name.endswith('AccessError'):
            return 'sin acceso'
        raise
    if not r:
        return None
    a = r[0]
    return (a['res_model'] or False, a['res_id'] or 0, (a['create_uid'] or [False])[0])


def preparar(adm):
    pwd = os.environ['E2P_TEST_PASS']
    gid = {}
    for x in ('base.group_user',) + FORBIDDEN:
        gid[x] = adm.kw('ir.model.data', 'xmlid_to_res_id', [x])
    if not gid['base.group_user']:
        sys.exit('No existe el grupo base.group_user')
    forbidden_ids = {gid[x]: x for x in FORBIDDEN if gid[x]}
    # Primero se comprueban los dos; solo si los dos están limpios se escribe algo.
    existing = {}
    for key, (login, _name) in LOGINS.items():
        uid = user_id(adm, login)
        if uid:
            u = adm.kw('res.users', 'read', [[uid], ['share', 'groups_id']])[0]
            bad = sorted(forbidden_ids[g] for g in u['groups_id'] if g in forbidden_ids)
            if u['share'] or bad:
                sys.exit('ABORTO: %s (id %s) ya existe y no es un interno de prueba (%s). '
                         'No se ha modificado nada.' % (login, uid, 'portal' if u['share'] else ', '.join(bad)))
            existing[key] = uid
    estado = {'inicio': (datetime.datetime.now(datetime.timezone.utc)
                         - datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')}
    for key, (login, name) in LOGINS.items():
        vals = {'groups_id': [(6, 0, [gid['base.group_user']])], 'password': pwd, 'active': True}
        if key in existing:
            uid = existing[key]
            adm.kw('res.users', 'write', [[uid], vals])
            what = 'reactivado'
        else:
            vals.update({'name': name, 'login': login})
            uid = adm.kw('res.users', 'create', [vals])
            what = 'creado'
        estado[key] = uid
        print('%-3s %-14s id %-5s %s (interno, sin más grupos)' % (key, login, uid, what))
    a2 = login_or_exit(LOGINS['A2'][0], pwd)
    estado['X'] = a2.kw('ir.attachment', 'create', [{
        'name': 'e2p-a2.txt', 'datas': 'ZTJwLWEyLWJvZHk=', 'mimetype': 'text/plain'}])
    save_state(estado)
    print('X (adjunto huérfano de A2) = %s' % estado['X'])
    print('Ids guardados en %s (sin secretos).' % ESTADO)


def prueba(adm):
    estado = load_state()
    pwd = os.environ['E2P_TEST_PASS']
    X, A2 = estado['X'], estado['A2']
    a2 = login_or_exit(LOGINS['A2'][0], pwd)
    b = login_or_exit(LOGINS['B'][0], pwd)

    x0 = att(adm, X)
    check('línea base: X huérfano y de A2', x0 == (False, 0, A2), x0, (False, 0, A2))
    if x0 != (False, 0, A2):
        sys.exit('X no está en el estado esperado: no sigo.')

    try:
        r = b.kw('chatboo.session', 'create', [{'name': 'E2P sesión de B (4 bis)'}])
    except RpcError as exc:
        check('B crea su sesión CS_B2', False, exc, 'id')
        sys.exit('B no pudo crear la sesión: no sigo.')
    cs2 = r if isinstance(r, int) else r[0]
    check('B crea su sesión CS_B2', True, cs2, 'id')
    estado['CS_B2'] = cs2
    save_state(estado)

    print("""
[ALTERA] Ahora engancha X a CS_B2 por SQL (simula un enganche anterior al parche; solo toca X = %d):

%s <<'SQL'
UPDATE ir_attachment SET res_model = 'chatboo.session', res_id = %d
 WHERE id = %d AND create_uid = %d AND res_model IS NULL;
SELECT id, res_model, res_id, create_uid FROM ir_attachment WHERE id = %d;
SQL

Esperado: UPDATE 1 y la fila  %d | chatboo.session | %d | %d
""" % (X, PSQL, cs2, X, A2, X, X, cs2, A2))
    input('Pulsa Intro cuando el UPDATE haya dado «UPDATE 1» (Ctrl+C para abortar)... ')

    x1 = att(b, X)  # B, dueño de CS_B2: admin no ve adjuntos de sesiones ajenas
    check('X enganchado a CS_B2 (tras el UPDATE, visto por B)', x1 == ('chatboo.session', cs2, A2), x1,
          ('chatboo.session', cs2, A2))
    if x1 != ('chatboo.session', cs2, A2):
        sys.exit('El enganche no está hecho: no sigo. CS_B2 queda para --limpiar.')

    try:
        z2 = b.kw('ir.attachment', 'create', [{
            'name': 'e2p-b-propio.txt', 'datas': 'ZTJwLWItcHJvcGlv', 'mimetype': 'text/plain',
            'res_model': 'chatboo.session', 'res_id': cs2}])
        check('B crea Z2, adjunto propio colgado de CS_B2', True, z2, 'id')
        estado['Z2'] = z2
        save_state(estado)
    except RpcError as exc:
        z2 = None
        check('B crea Z2, adjunto propio colgado de CS_B2', False, exc, 'id')

    try:
        r = b.kw('chatboo.session', 'unlink', [[cs2]])
        check('B borra su sesión CS_B2 (unlink)', r is True, r, True)
    except RpcError as exc:
        check('B borra su sesión CS_B2 (unlink)', False, exc, True)
    left = b.kw('chatboo.session', 'search_count', [[('id', '=', cs2)]])
    check('CS_B2 ya no existe', left == 0, left, 0)
    if z2:
        z = att(adm, z2)
        check('Z2 (de B) borrado con la sesión', z is None, z, None)
    xa = att(adm, X)
    check('X: res_model vacío, res_id 0, create_uid A2', xa == (False, 0, A2), xa, (False, 0, A2))
    st = a2.get('/pns_ai_mcp/session_file/%d' % X)
    check('A2: GET session_file/X (sigue siendo suyo)', st == 200, st, 200)
    st = b.get('/pns_ai_mcp/session_file/%d' % X)
    check('B: GET session_file/X', st == 404, st, 404)
    print('\nRESULTADO: %s' % ('TODO OK' if not fallos else '%d INESPERADOS' % fallos))
    return 1 if fallos else 0


def limpiar(adm):
    estado = {}
    if os.path.exists(ESTADO):
        with open(ESTADO) as fh:
            estado = json.load(fh)
    pwd = os.environ.get('E2P_TEST_PASS')
    for key, (login, _n) in LOGINS.items():
        if not user_id(adm, login):
            continue
        if not pwd:
            print('Sin E2P_TEST_PASS: no se borran las sesiones de %s' % login)
            continue
        try:
            s = Session(login, pwd)
        except RpcError as exc:
            print('No se pudo entrar como %s (%s): sus sesiones quedan' % (login, exc))
            continue
        try:
            ses = s.kw('chatboo.session', 'search', [[('user_id', '=', s.uid)]])
            if ses:
                s.kw('chatboo.session', 'unlink', [ses])
            print('Sesiones de %s: %s' % (login, ses or 'ninguna'))
        except RpcError as exc:
            print('Sesiones de %s: NO borradas (%s)' % (login, exc))
    wanted = [a for a in (estado.get(k) for k in ('X', 'Z2')) if a]
    atts = []
    for a in wanted:  # read y no search: ver att()
        st = att(adm, a)
        if st == 'sin acceso':
            print('Adjunto %s: admin no tiene acceso (cuelga de una sesión ajena que sigue viva)' % a)
        elif st is not None:
            atts.append(a)
    if atts:
        try:
            adm.kw('ir.attachment', 'unlink', [atts])
            print('Adjuntos de prueba %s: borrados' % atts)
        except RpcError as exc:
            print('Adjuntos de prueba %s: NO borrados (%s)' % (atts, exc))
    else:
        print('Adjuntos de prueba: ninguno')
    for key, (login, _n) in LOGINS.items():
        uid = user_id(adm, login)
        if not uid:
            print('No existe %s' % login)
            continue
        partner = adm.kw('res.users', 'read', [[uid], ['partner_id']])[0]['partner_id']
        try:
            adm.kw('res.users', 'unlink', [[uid]])
        except RpcError as exc:
            adm.kw('res.users', 'write', [[uid], {'active': False}])
            print('No se pudo borrar %s (%s): archivado' % (login, exc))
            continue
        if partner:
            try:
                adm.kw('res.partner', 'unlink', [[partner[0]]])
                print('Borrado %s (id %s) y su contacto' % (login, uid))
            except RpcError as exc:
                print('Borrado %s (id %s); su contacto no (%s)' % (login, uid, exc))
        else:
            print('Borrado %s (id %s)' % (login, uid))
    return 0


if __name__ == '__main__':
    adm = login_or_exit(os.environ.get('E2P_ADM_LOGIN', 'admin'), os.environ['E2P_ADM_PASS'])
    try:
        if '--preparar' in sys.argv:
            preparar(adm)
            sys.exit(0)
        if '--limpiar' in sys.argv:
            sys.exit(limpiar(adm))
        sys.exit(prueba(adm))
    except RpcError as exc:
        sys.exit('ERROR: %s' % exc)
