#!/usr/bin/env python3
# Copyright 2026 Seges
# License Apache-2.0 (https://www.apache.org/licenses/LICENSE-2.0).
"""Pruebas manuales de E3′ (parches 25 a 28) en lab_pns_ai_3879_14.

Lo ejecuta Sergio (docs/pendiente/lab_e3_3879.md). Solo biblioteca estándar.
Pide las contraseñas con getpass y no imprime secretos.

    python3 pruebas_e3p_lab.py preparar   # P-8d y P-8e: contactos y compañía de prueba
    python3 pruebas_e3p_lab.py rpc        # P-8c y P-8h por XML-RPC
    python3 pruebas_e3p_lab.py http       # P-8e b y X-Frame-Options: cabeceras y CSP servida
    python3 pruebas_e3p_lab.py limpiar    # borra lo que han creado los pasos anteriores

Variables: E3P_URL (por defecto http://localhost:8169), E3P_DB (lab_pns_ai_3879_14) y
E3P_SESSION (id de una chatboo_session de admin, para P-8c y la carcasa).
"""
import base64
import getpass
import html
import http.cookiejar
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.request
import xmlrpc.client
import zlib

URL = os.environ.get('E3P_URL', 'http://localhost:8169').rstrip('/')
DB = os.environ.get('E3P_DB', 'lab_pns_ai_3879_14')
TAG = 'Seges E3'
EVIL = TAG + ' </script><script>alert("P-8e")</script>'
EVIL_COMMENT = TAG + ' <!--<script>'
# Prefijo fijo del parche 27 b (tras la revisión de E3′, B1): doctype, charset y CSP.
CSP_START = '<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy"'
# Diseño de P-8e b: pide recursos externos y red. Con la CSP, nada sale.
DESIGN_NET = (
    '<!DOCTYPE html><html><head><title>Seges E3 P-8e b</title>'
    '<link rel="stylesheet" href="https://example.com/seges-e3.css">'
    '<style>@import url("https://example.com/seges-e3-font.css");</style>'
    '</head><body><h1>Seges E3 P-8e b</h1><p id="out">sin script</p>'
    '<img src="https://example.com/seges-e3.png" alt="externa">'
    '<script>document.getElementById("out").textContent = "script en linea: ok";'
    'try { fetch("https://example.com/seges-e3"); } catch (e) {}'
    'try { navigator.sendBeacon("https://example.com/seges-e3", "x"); } catch (e) {}'
    '</script></body></html>'
)
DESIGN_PLAIN = (
    '<!DOCTYPE html><html><head><title>Seges E3 P-8h</title></head>'
    '<body><p>Seges E3 P-8h</p></body></html>'
)
STATE = os.path.expanduser('~/lab_e3p/estado_e3p.json')


def _png_base64():
    """PNG de 16x16 rojo, sin Pillow."""
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body))
    raw = b''.join(b'\x00' + b'\xc8\x1e\x1e' * 16 for _ in range(16))
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    return base64.b64encode(png).decode()


def _load():
    try:
        with open(STATE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, 'w') as fh:
        json.dump(state, fh, indent=1)


class Rpc:
    def __init__(self, login):
        self.login = login
        self.password = getpass.getpass('Contraseña de %s: ' % login)
        common = xmlrpc.client.ServerProxy(URL + '/xmlrpc/2/common')
        self.uid = common.authenticate(DB, login, self.password, {})
        if not self.uid:
            sys.exit('No se pudo entrar como %s' % login)
        self.models = xmlrpc.client.ServerProxy(URL + '/xmlrpc/2/object', allow_none=True)

    def call(self, model, method, args, kwargs=None):
        try:
            return 'ok', self.models.execute_kw(
                DB, self.uid, self.password, model, method, args, kwargs or {},
            )
        except xmlrpc.client.Fault as fault:
            lines = [ln for ln in fault.faultString.strip().splitlines() if ln.strip()]
            return 'error', (lines[-1] if lines else fault.faultString)[:220]


def _show(case, expected, result):
    status, value = result
    shown = value if status == 'error' else repr(value)[:120]
    print('%-7s esperado: %-34s -> %s: %s' % (case, expected, status, shown))


def preparar():
    admin = Rpc('admin')
    state = _load()
    png = _png_base64()
    main_id = admin.call('res.users', 'read', [[admin.uid], ['company_id']])[1][0]['company_id'][0]
    status, company_id = admin.call('res.company', 'create', [{'name': TAG + ' otra'}])
    print('compañía', status, company_id)
    # El contacto oculto se crea antes de quitarle la compañía a admin: la regla
    # multicompañía también aplica al crear.
    status, hidden = admin.call('res.partner', 'create', [{
        'name': TAG + ' foto oculta', 'company_id': company_id, 'image_1920': png,
    }])
    # res.company.create la añade a admin: se le quita para que el contacto quede oculto.
    print('admin sin la compañía', admin.call('res.users', 'write', [[admin.uid], {
        'company_ids': [(3, company_id)], 'company_id': main_id,
    }])[0])
    status2, visible = admin.call('res.partner', 'create', [{
        'name': TAG + ' foto visible', 'company_id': False, 'image_1920': png,
    }])
    status3, evil = admin.call('res.partner', 'create', [[{'name': EVIL}, {'name': EVIL_COMMENT}]])
    print('contactos', status, status2, status3)
    state.update({'company_id': company_id, 'hidden': hidden, 'visible': visible,
                  'evil': evil if status3 == 'ok' else []})
    _save(state)
    print('P-8d: oculto res.partner %s (otra compañía), visible res.partner %s' % (hidden, visible))
    print('      /web/image/res.partner/%s/image_128 y /web/image/res.partner/%s/image_128'
          % (hidden, visible))
    print('P-8e a: contactos %s' % state['evil'])
    print('Comprobación: admin no ve el oculto ->',
          admin.call('res.partner', 'search_count', [[('id', '=', hidden)]]))


def rpc():
    admin = Rpc('admin')
    demo = Rpc('demo')
    state = _load()
    session = int(os.environ.get('E3P_SESSION') or 0)
    ids = admin.call('res.users', 'search', [[('login', 'in', ['demo', 'portal'])]])[1]
    logins = dict((u['login'], u['id']) for u in admin.call(
        'res.users', 'read', [ids, ['login']])[1])
    demo_id, portal_id = logins.get('demo'), logins.get('portal')
    print('== P-8c (parche 25), sesión de admin %s' % session)
    before = admin.call('chatboo.session', 'read', [[session], ['canvas_rev']])
    _show('P-8c1', 'AttributeError (no existe)', demo.call(
        'chatboo.session', 'paint_canvas', [[session], TAG]))
    _show('P-8c2', 'AccessError (privado)', demo.call(
        'chatboo.session', '_paint_canvas', [[session], TAG]))
    _show('P-8c3', 'AttributeError (no existe)', admin.call(
        'chatboo.session', 'paint_canvas', [[session], TAG]))
    after = admin.call('chatboo.session', 'read', [[session], ['canvas_rev']])
    print('P-8c4   canvas_rev antes %s, después %s (iguales)' % (before[1], after[1]))

    print('== P-8h (parche 28)')
    status, page_a = admin.call('chatboo.canvas.page', 'create', [{
        'name': TAG + ' P-8h admin', 'design': DESIGN_PLAIN,
    }])
    _show('P-8h1', 'ok (página propia)', (status, page_a))
    _show('P-8h2', 'AccessError (owner_id)', admin.call(
        'chatboo.canvas.page', 'write', [[page_a], {'owner_id': demo_id}]))
    _show('P-8h3', 'ValidationError (portal)', admin.call(
        'chatboo.canvas.page', 'write', [[page_a], {'user_ids': [(4, portal_id)]}]))
    _show('P-8h4', 'ok (interno)', admin.call(
        'chatboo.canvas.page', 'write', [[page_a], {'user_ids': [(4, demo_id)]}]))
    status, page_d = demo.call('chatboo.canvas.page', 'create', [{
        'name': TAG + ' P-8h demo', 'design': DESIGN_PLAIN,
    }])
    _show('P-8h5', 'ok (página de demo)', (status, page_d))
    _show('P-8h6', 'AccessError (owner_id)', demo.call(
        'chatboo.canvas.page', 'write', [[page_d], {'owner_id': admin.uid}]))
    _show('P-8h7', 'ok (el admin la lee)', admin.call(
        'chatboo.canvas.page', 'read', [[page_d], ['name', 'owner_id']]))
    _show('P-8h8', 'AccessError (regla)', admin.call(
        'chatboo.canvas.page', 'write', [[page_d], {'name': TAG + ' cambiada'}]))
    _show('P-8h9', 'AccessError (Stop sharing)', admin.call(
        'chatboo.canvas.page', 'action_unshare', [[page_d]]))
    _show('P-8h10', 'AccessError (alta para otro)', admin.call(
        'chatboo.canvas.page', 'create', [{
            'name': TAG + ' para demo', 'design': DESIGN_PLAIN, 'owner_id': demo_id,
        }]))
    status, page_d2 = demo.call('chatboo.canvas.page', 'create', [{
        'name': TAG + ' P-8h demo, para la interfaz', 'design': DESIGN_PLAIN,
        'user_ids': [(4, admin.uid)],
    }])
    _show('P-8h11', 'ok (el admin la borra)', admin.call(
        'chatboo.canvas.page', 'unlink', [[page_d]]))
    state.update({'page_admin': page_a, 'page_demo_ui': page_d2})
    _save(state)
    print('Para la interfaz (P-8h, «Stop sharing»): página de admin %s y de demo %s'
          % (page_a, page_d2))


def _opener(login):
    password = getpass.getpass('Contraseña de %s (HTTP): ' % login)
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    body = json.dumps({'jsonrpc': '2.0', 'params': {
        'db': DB, 'login': login, 'password': password,
    }}).encode()
    req = urllib.request.Request(
        URL + '/web/session/authenticate', data=body,
        headers={'Content-Type': 'application/json'},
    )
    answer = json.loads(opener.open(req).read().decode())
    if not (answer.get('result') or {}).get('uid'):
        sys.exit('No se pudo entrar como %s por HTTP' % login)
    return opener


def _csp_first(doc):
    """Lo servido empieza por el prefijo fijo: nada del diseño va antes."""
    return doc.startswith(CSP_START)


def http_check():
    state = _load()
    opener = _opener('admin')
    admin = Rpc('admin')
    status, page_net = admin.call('chatboo.canvas.page', 'create', [{
        'name': TAG + ' P-8e b', 'design': DESIGN_NET,
    }])
    print('P-8e b: página %s %s' % (status, page_net))
    state['page_net'] = page_net
    _save(state)
    session = int(os.environ.get('E3P_SESSION') or 0)
    routes = [('/chatboo/page/%s' % page_net, True)]
    if session:
        routes.insert(0, ('/chatboo/canvas/%s' % session, True))
    routes += [('/chatboo/page/%s/download' % page_net, False)]
    if session:
        routes.append(('/chatboo/canvas/%s/download' % session, False))
    for path, shell in routes:
        try:
            resp = opener.open(URL + path)
        except urllib.error.HTTPError as err:
            print('%-40s HTTP %s' % (path, err.code))
            continue
        text = resp.read().decode('utf-8', 'replace')
        if shell:
            found = re.search(r'srcdoc="([^"]*)"', text)
            doc = html.unescape(found.group(1)) if found else ''
        else:
            doc = text
        print('%-40s HTTP %s · X-Frame-Options: %s · empieza por el prefijo CSP: %s'
              % (path, resp.status, resp.headers.get('X-Frame-Options'),
                 _csp_first(doc) if doc else 'sin diseño'))
    print('Abrir en el navegador: %s/chatboo/page/%s (consola: bloqueos por CSP)'
          % (URL, page_net))


def _existing(admin, model, ids, context=None):
    """Ids de la lista que siguen existiendo: limpiar se puede repetir a medias."""
    status, found = admin.call(model, 'search', [[('id', 'in', ids)]],
                               {'context': context} if context else None)
    # Si la búsqueda falla, se intenta con todos y el unlink dice el error.
    return found if status == 'ok' else ids


def _unlink_properties(admin, company_id, name):
    """Borra las ir.property de la compañía de prueba con una acción de servidor temporal.

    admin no puede hacerlo por XML-RPC: la ACL de ir.property no da perm_unlink a
    base.group_system (ir.model.access.csv:24 del core 14.0). Tampoco basta un write a
    company_id False: res.company.create crea una propiedad de la tarifa sin res_id y el
    índice ir_property_unique_index, (fields_id, COALESCE(company_id, 0), COALESCE(res_id, '')),
    choca con la que dejó sin compañía un borrado anterior (y si no la hay, la deja huérfana).
    El sudo se limita a las propiedades de esa compañía, que la acción vuelve a comprobar
    por id y nombre.
    """
    code = (
        "c = env['res.company'].sudo().search([('id', '=', %r), ('name', '=', %r)])\n"
        "if c:\n"
        "    props = env['ir.property'].sudo().search([('company_id', '=', c.id)])\n"
        "    count = len(props)\n"
        "    props.unlink()\n"
        "    action = {'propiedades': count}\n"
        "else:\n"
        "    action = {'propiedades': 0, 'aviso': 'la compañía no existe o no es de prueba'}\n"
    ) % (company_id, name)
    status, model = admin.call('ir.model', 'search', [[('model', '=', 'res.company')]])
    if status != 'ok' or not model:
        print('propiedades', status, model)
        return
    status, action_id = admin.call('ir.actions.server', 'create', [{
        'name': TAG + ' limpiar propiedades', 'model_id': model[0], 'state': 'code', 'code': code,
    }])
    if status != 'ok':
        print('propiedades', status, action_id)
        return
    try:
        status, result = admin.call('ir.actions.server', 'run', [[action_id]])
        if status == 'ok' and isinstance(result, dict):
            print('propiedades', status, result.get('propiedades'), result.get('aviso', ''))
        else:
            print('propiedades', status, result)
    finally:
        print('acción temporal', admin.call('ir.actions.server', 'unlink', [[action_id]]))


def limpiar():
    admin = Rpc('admin')
    state = _load()
    pages = [state.get(k) for k in ('page_admin', 'page_demo_ui', 'page_net') if state.get(k)]
    if pages:
        pages = _existing(admin, 'chatboo.canvas.page', pages)
        if pages:
            print('páginas', admin.call('chatboo.canvas.page', 'unlink', [pages]))
        else:
            print('páginas ya borradas')
    company_id = state.get('company_id')
    company_name = TAG + ' otra'
    if company_id:
        # Solo se toca si sigue siendo la de preparar (admin la ve: regla erp manager).
        status, found = admin.call('res.company', 'search_read', [[('id', '=', company_id)]],
                                   {'fields': ['name']})
        if status != 'ok':
            print('compañía', (status, found))
            company_id = None
        elif not found:
            print('compañía ya borrada')
            company_id = None
        elif found[0]['name'] != company_name:
            print('compañía %s no es de prueba: no se toca' % company_id)
            company_id = None
    if company_id:
        # El contacto oculto es de esa compañía: sin ella, la regla multicompañía
        # impide a admin borrarlo (y la llamada no borraría ninguno de los cuatro).
        print('admin con la compañía', admin.call('res.users', 'write', [[admin.uid], {
            'company_ids': [(4, company_id)]}])[0])
    partners = [state.get('hidden'), state.get('visible')] + list(state.get('evil') or [])
    partners = [p for p in partners if isinstance(p, int)]
    if partners:
        partners = _existing(admin, 'res.partner', partners, {'active_test': False})
        if partners:
            print('contactos', admin.call('res.partner', 'unlink', [partners]))
        else:
            print('contactos ya borrados')
    if company_id:
        # Con sudo da igual que admin tenga o no la compañía: se hace antes de quitársela.
        _unlink_properties(admin, company_id, company_name)
        print('admin sin la compañía', admin.call('res.users', 'write', [[admin.uid], {
            'company_ids': [(3, company_id)]}])[0])
        # En Odoo 14 res.company no se archiva: se borra (si algo la usa, lo dice el error).
        print('compañía', admin.call('res.company', 'unlink', [[company_id]]))
    print('Queda el archivo de estado:', STATE)


if __name__ == '__main__':
    steps = {'preparar': preparar, 'rpc': rpc, 'http': http_check, 'limpiar': limpiar}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        sys.exit(__doc__)
    steps[sys.argv[1]]()
