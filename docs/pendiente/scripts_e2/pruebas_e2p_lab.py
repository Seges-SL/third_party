#!/usr/bin/env python3
"""P-19 y P-37 de E2′ en el laboratorio lab_pns_ai_3879, por /mcp (relaxaicode, sin LLM) y call_kw.

Biblioteca estándar. Claves y contraseñas, del entorno:
  E2P_URL (http://localhost:8169), E2P_DB (lab_pns_ai_3879_14),
  E2P_ADM_LOGIN (admin), E2P_ADM_PASS, E2P_KEY_ADM (clave MCP de admin),
  E2P_SECRET_ID (id de database.secret, del SELECT previo)
  E2P_FORZAR_NO_RECHAZO=1 (solo para validar el script): trata el control r1 como un caso de
        secreto. r1 responde, así que debe salir INESPERADO con el marcador «NO RECHAZADO» y el tipo.

  P-19  admin (AI Administrator con Ajustes), relaxaicode: diez vías al secreto -> todas con
        «cannot be read from the RelaxAICode sandbox» (o rechazo de la puerta); dos controles
        (nombre del proveedor y search_read sin campos de ai.log) -> responden.
        h, read_group con alias; i, browse con id decimal; j, leer el proveedor después de
        page_url (revisión del 27/10/2026, rechazo del parche 18).
  P-101 admin, relaxaicode: env.all, env.cache, x = env; x.all y getattr compuesto -> rechazo
        «it is the ORM's own state» (parche 23); all([...]) -> responde.
  P-37  admin por call_kw: write y create en ai.change.journal -> AccessError «Only the system can
        write the AI change journal.»; la fila 1 sin cambios (lo confirma el SELECT de después).

No imprime secretos. En los casos que deben rechazarse (P-19 a-j y P-101 a-e):
  - rechazados: el mensaje de rechazo (200 caracteres, con las cadenas largas tipo clave tapadas);
  - no rechazados: solo «NO RECHAZADO (tipo: …)», con isError, los tipos de content y si el
    resultado está vacío ([], {}, '', None, False, 0); nunca el contenido ni su longitud.
    «vacío» indica que el caso no llegó a probar la vía (P-19b sin proveedores en el agente);
  - error JSON-RPC: solo su código; error HTTP en tools/call: solo el código HTTP, sin el cuerpo.
Los controles (r1, r2, P-101r), P-37 y P-37b muestran su respuesta como hasta ahora.
"""
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get('E2P_URL', 'http://localhost:8169').rstrip('/')
DB = os.environ.get('E2P_DB', 'lab_pns_ai_3879_14')
GUARD = 'cannot be read from the RelaxAICode sandbox'
FORZAR = os.environ.get('E2P_FORZAR_NO_RECHAZO') == '1'
fallos = 0


def db_cookie():
    """Sesión anónima atada a DB: /mcp es auth='none' y el laboratorio tiene varias BD."""
    jar = http.cookiejar.CookieJar()
    urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(
        BASE + '/web/login?db=' + DB, timeout=60).read()
    return '; '.join('%s=%s' % (c.name, c.value) for c in jar if c.name == 'session_id')


class Web:
    def __init__(self, login, pwd):
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        r = self.post('/web/session/authenticate', {'db': DB, 'login': login, 'password': pwd})
        if not (r.get('result') or {}).get('uid'):
            sys.exit('No se pudo iniciar sesión como %s' % login)

    def post(self, path, params):
        body = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': params}).encode()
        req = urllib.request.Request(BASE + path, data=body,
                                     headers={'Content-Type': 'application/json'})
        with self.op.open(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    def kw_raw(self, model, method, args, kwargs=None):
        return self.post('/web/dataset/call_kw/%s/%s' % (model, method),
                         {'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {}})


class Mcp:
    def __init__(self, key, tool):
        self.key, self.sid, self.n, self.cookie = key, None, 0, db_cookie()
        self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                'clientInfo': {'name': 'seges-e2p-lab', 'version': '1'}})
        self.rpc('notifications/initialized', notify=True)
        tools = self.rpc('tools/list').get('tools', [])
        self.tool = next((t for t in tools if t.get('name') == tool), None)
        if not self.tool:
            sys.exit('Esta clave no ve la herramienta %s' % tool)

    def rpc(self, method, params=None, notify=False):
        self.n += 1
        msg = {'jsonrpc': '2.0', 'method': method, 'params': params or {}}
        if not notify:
            msg['id'] = self.n
        h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
             'X-MCP-API-Key': self.key, 'Cookie': self.cookie}
        if self.sid:
            h['Mcp-Session-Id'] = self.sid
        req = urllib.request.Request(BASE + '/mcp', data=json.dumps(msg).encode(), headers=h)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.sid = resp.headers.get('Mcp-Session-Id') or self.sid
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            if method == 'tools/call':
                # El cuerpo de un error de tools/call puede arrastrar valores del código ejecutado.
                sys.exit('HTTP %s en %s (cuerpo omitido)' % (exc.code, method))
            sys.exit('HTTP %s en %s: %s' % (exc.code, method, exc.read().decode()[:300]))
        if not raw.strip():
            return {}
        if raw.lstrip().startswith('data:') or '\ndata:' in raw:
            raw = [l[5:].strip() for l in raw.splitlines() if l.startswith('data:')][-1]
        data = json.loads(raw)
        return {'_error': data['error']} if 'error' in data else (data.get('result') or {})

    def code(self, code):
        res = self.rpc('tools/call', {'name': self.tool['name'], 'arguments': {'code': code}})
        text = ' '.join(c.get('text', '') for c in res.get('content') or [] if isinstance(c, dict))
        return res, text


VACIOS = ('', '[]', '{}', '()', 'None', 'null', 'False', 'false', '0', '""', "''")


def is_empty(res):
    """True si el resultado no trae nada: sin mirar ni devolver el contenido.

    relaxaicode puede envolver el resultado en un dict con claves internas (__phase__…):
    se descartan las claves que empiezan por '__' y se desenvuelve 'result' o 'data'."""
    if 'structuredContent' in res:
        valor = res['structuredContent']
    else:
        texto = ' '.join(c.get('text', '') for c in res.get('content') or []
                         if isinstance(c, dict)).strip()
        try:
            valor = json.loads(texto)
        except ValueError:
            return texto in VACIOS
    if isinstance(valor, dict):
        valor = {k: v for k, v in valor.items() if not str(k).startswith('__')}
        if len(valor) == 1 and next(iter(valor)) in ('result', 'data'):
            valor = next(iter(valor.values()))
    if isinstance(valor, str):
        return valor.strip() in VACIOS
    return valor in ([], {}, None, False, 0)


def kind(res):
    """Tipo de una respuesta de tools/call, sin nada de su contenido ni su longitud."""
    if '_error' in res:
        err = res['_error']
        return 'error JSON-RPC %s' % (err.get('code') if isinstance(err, dict) else '?')
    tipos = [c.get('type', '?') if isinstance(c, dict) else type(c).__name__
             for c in res.get('content') or []]
    extra = ', structuredContent' if 'structuredContent' in res else ''
    return 'isError=%s, content=[%s]%s, %s' % (bool(res.get('isError')), ', '.join(tipos), extra,
                                             'vacío' if is_empty(res) else 'no vacío')


def tapa(texto):
    """Tapa cadenas largas tipo clave o token en un mensaje de rechazo."""
    return re.sub(r'[A-Za-z0-9_+/=\-]{24,}', '<…>', texto)


def check(pr, what, ok, got, res=None):
    """res solo en los casos que deben rechazarse: entonces nunca se imprime una respuesta."""
    global fallos
    fallos += 0 if ok else 1
    print('%-6s %-62s %s' % (pr, what[:62], 'OK' if ok else 'INESPERADO'))
    if res is None:
        shown = got if got not in ('', None) else '(sin texto)'
    elif res.get('isError'):
        shown = tapa(str(got)) if got else '(rechazo sin texto)'
    else:
        shown = 'NO RECHAZADO (tipo: %s)' % kind(res)
    print('       -> %s' % str(shown).replace('\n', ' ')[:200])


m = Mcp(os.environ['E2P_KEY_ADM'], 'relaxaicode')
SECRET_ID = int(os.environ['E2P_SECRET_ID'])  # id de database.secret (SELECT del documento)
REFUSED = (
    ('a', "result = env['ai.log'].search([('provider_id', '!=', False)], limit=1)"
          ".provider_id.api_key"),
    ('b', "result = [l.provider_id.api_key for l in "
          "env.ref('pns_ai_mcp.ai_agent_admin').provider_ids]"),
    ('c', "p = env['ai.log'].search([('provider_id', '!=', False)], limit=1).provider_id.id\n"
          "result = env['ai.log'].new({'provider_id': p}).provider_id.api_key"),
    ('d', "p = env['ai.log'].search([('provider_id', '!=', False)], limit=1).provider_id.id\n"
          "result = env['mail.template.preview'].new("
          "{'resource_ref': 'ai.provider,%d' % p}).resource_ref.api_key"),
    ('e', "result = env['ai.log'].search_count([('provider_id.api_key', '=like', 'A%')])"),
    ('f', "p = env['mail.template.preview'].new("
          "{'resource_ref': 'ir.config_parameter,%d'})\n"
          "result = [p.resource_ref.key, p.resource_ref.value]" % SECRET_ID),
    ('g', "result = env['ai.log'].search([('provider_id', '!=', False)], limit=1)"
          ".provider_id.read(['api_key'])"),
    # h: read_group con alias, en ir.config_parameter y en ai.provider.
    ('h1', "p = env['mail.template.preview'].new("
           "{'resource_ref': 'ir.config_parameter,%d'}).resource_ref\n"
           "result = p.read_group([('key', '=', 'database.secret')],"
           " ['display_name:max(value)'], ['key'])" % SECRET_ID),
    ('h2', "p = env['ai.log'].search([('provider_id', '!=', False)], limit=1).provider_id\n"
           "result = p.read_group([('id', '=', p.id)], ['display_name:max(api_key)'], ['name'])"),
    # i: browse con id decimal (y con str).
    ('i1', "p = env['mail.template.preview'].new("
           "{'resource_ref': 'ir.config_parameter,%d'}).resource_ref\n"
           "result = p.browse([p.id * 1.0]).value" % SECRET_ID),
    ('i2', "p = env['mail.template.preview'].new("
           "{'resource_ref': 'ir.config_parameter,%d'}).resource_ref\n"
           "result = p.browse(str(p.id)).value" % SECRET_ID),
    # j: el proveedor después de page_url. Por /mcp no hay sesión de Chatboo y page_url
    # devuelve '' sin abrir la ventana: con la ventana real lo cubren los tests
    # (test_cache_closed_after_window_prefetch) y R8 en E3′.
    ('j', "try:\n"
          "    page_url([{'Mes': '2026-10', 'Ventas': 1}], 'seges p-19j')\n"
          "except NameError:\n"
          "    pass\n"
          "result = env['ai.log'].search([('provider_id', '!=', False)], limit=1)"
          ".provider_id.api_key"),
)
for via, code in REFUSED:
    res, text = m.code(code)
    check('P-19' + via, 'rechazo del campo secreto', bool(res.get('isError')) and (
        GUARD in text or 'not allowed' in text.lower()), text, res)

res, text = m.code("result = {'data': [{'proveedor': env['ai.log'].search("
                   "[('provider_id', '!=', False)], limit=1).provider_id.name}]}")
if FORZAR:
    check('P-19r1', 'FORZADO: r1 tratado como caso de secreto', bool(res.get('isError')) and (
        GUARD in text or 'not allowed' in text.lower()), text, res)
else:
    check('P-19r1', 'control: nombre del proveedor', not res.get('isError'), text or json.dumps(res)[:400])
res, text = m.code("result = env['ai.log'].search_read([('provider_id', '!=', False)], limit=1)")
check('P-19r2', 'control: search_read de ai.log sin campos', not res.get('isError'),
      text or json.dumps(res)[:400])

# P-101 (parche 23): el env del sandbox no lleva a los entornos reales del hilo. Solo lectura.
ENV_STATE = "it is the ORM's own state"
for via, code in (
        ('a', "result = type(env.all).__name__"),
        ('b', "result = type(env.cache).__name__"),
        ('c', "x = env\nresult = type(x.all).__name__"),
        ('d', "result = [e.uid for e in getattr(env, 'al' + 'l')]"),
        ('e', "result = type(getattr(env, 'ca' + 'che')).__name__"),
):
    res, text = m.code(code)
    check('P-101' + via, 'rechazo: estado del ORM', bool(res.get('isError')) and ENV_STATE in text
          and 'Environments' not in text, text, res)
res, text = m.code("result = {'data': [{'all': all([1, 2]), 'uid': env.uid, 'login': env.user.login}]}")
check('P-101r', 'control: all([...]), env.uid y env.user', not res.get('isError'),
      text or json.dumps(res)[:400])

adm = Web(os.environ.get('E2P_ADM_LOGIN', 'admin'), os.environ['E2P_ADM_PASS'])
after = json.dumps({'ids': [999999], 'meta': {'quarantine': True}})
r = adm.kw_raw('ai.change.journal', 'write', [[1], {
    'op': 'unlink', 'state': 'applied', 'reversible': True, 'model_name': 'res.partner',
    'after_json': after}])
d = (r.get('error') or {}).get('data') or {}
check('P-37w', 'write en el diario: AccessError', d.get('name') == 'odoo.exceptions.AccessError',
      d.get('message') or r)
r = adm.kw_raw('ai.change.journal', 'create', [{
    'op': 'unlink', 'state': 'applied', 'reversible': True, 'model_name': 'res.partner',
    'after_json': after}])
d = (r.get('error') or {}).get('data') or {}
check('P-37c', 'create en el diario: AccessError', d.get('name') == 'odoo.exceptions.AccessError',
      d.get('message') or r)

# P-37b (opcional): demo propone borrar la etiqueta de prueba; Sergio confirma como demo en la interfaz.
if os.environ.get('E2P_KEY_DEMO') and os.environ.get('E2P_P37B_CAT'):
    cat = int(os.environ['E2P_P37B_CAT'])
    md = Mcp(os.environ['E2P_KEY_DEMO'], 'safe_plan_request')
    res = md.rpc('tools/call', {'name': md.tool['name'], 'arguments': {
        'title': 'Seges P-37b', 'steps': [
            {'op': 'unlink', 'model': 'res.partner.category', 'ids': [cat]}]}})
    text = ' '.join(c.get('text', '') for c in res.get('content') or [] if isinstance(c, dict))
    check('P-37b', 'propuesta creada (se confirma en Autorizaciones)',
          not res.get('isError') and 'verification_id' in text, text)
print('\nInesperados: %d' % fallos)
sys.exit(1 if fallos else 0)
