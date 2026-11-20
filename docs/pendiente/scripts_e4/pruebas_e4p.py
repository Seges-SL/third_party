#!/usr/bin/env python3
# Copyright 2026 Seges
# License Apache-2.0 (https://www.apache.org/licenses/LICENSE-2.0).
"""Pruebas de E4′ (parches 30 a 33) por XML-RPC en el staging pns_demo.

Lo ejecuta Sergio. Solo biblioteca estándar (Python 3.7.3 o posterior). Pide las
contraseñas con getpass, una por usuario y solo cuando hace falta, y no imprime secretos.

    python3 pruebas_e4p.py preparar   # admin: acción de confianza seges.e4p, archivada
    python3 pruebas_e4p.py rpc        # P-30, P-31, P-33 y P-32 por XML-RPC
    python3 pruebas_e4p.py limpiar    # admin: borra las acciones seges.e4p*

Variables: E4P_URL y E4P_DB (obligatorias), E4P_STATE (por defecto
~/staging_e4p/estado_e4p.json), E4P_ADMIN (admin), E4P_INTERNO (demo) y
E4P_AIADMIN (e1p_aiadmin).

Salida: 0 todo OK; 1 alguna comprobación FALLO; 2 parada (precondición, conexión,
autenticación o estado ausente).
"""
import datetime
import getpass
import http.client
import json
import os
import socket
import sys
import time
import xmlrpc.client
from xml.parsers.expat import ExpatError

DEFAULT_STATE = '~/staging_e4p/estado_e4p.json'
# Solo ante un 503 (el proxy del staging mientras Odoo arranca). Constantes del
# módulo para poder bajarlas en las pruebas del script.
RETRIES = 3
WAIT = 15
TIMEOUT = 120
# La consulta de P-30 mira desde t0 menos este margen, por si el reloj del equipo
# y el del servidor no coinciden.
T0_MARGIN = 300

CODE = 'seges.e4p'
LOG_ENDPOINT = 'seges_e4p_staging'
AGENT = 'pns_ai_mcp'
MISSING_AGENT = 'seges_e4p_no_existe'
MESSAGES = [{'role': 'user', 'content': 'x'}]
# faultCode de /xmlrpc/2 (odoo/service/wsgi_server.py:30-50 de Odoo 14).
FAULT_OTHER, FAULT_USER, FAULT_DENIED, FAULT_ACCESS = 1, 2, 3, 4
MSG_30 = ('Only internal users can write AI History rows.',
          'Only the system can write AI History rows for another user.')
MSG_31 = ('Only the system can call chat_completion.',)
MSG_32 = ('Only a Settings administrator can change trusted actions.',)
# Los cinco grupos de IA de pns_ai_mcp (security/security_groups.xml).
AI_GROUPS = tuple('pns_ai_mcp.' + name for name in (
    'group_ai_writer', 'group_ai_external_url', 'group_ai_external_api',
    'group_ai_conversational', 'group_ai_admin',
))
# (método, args JSON sin ids, kwargs JSON) de los cinco log_* que escriben, como en
# test_seges_e4p.py; solo log_llm_inference admite endpoint.
LOG_CALLS = (
    ('log_role_without_provider', [AGENT, 'conversation'], {}),
    ('log_provider_llm_request', [False], {'agent_code': AGENT}),
    ('log_provider_llm_response', [False],
     {'agent_code': AGENT, 'content_preview': 'seges'}),
    ('log_llm_inference', [False, {'total_tokens': 1}], {'endpoint': LOG_ENDPOINT}),
    ('log_provider_inference', [False, [], {}], {}),
)
WIZARD = 'ai.provider.usage.wizard'
WIZARD_FIELDS = ['total_tokens', 'cost_display']
ONCHANGE_SPEC = {'provider_id': '', 'total_tokens': '', 'cost_display': ''}
# Cifras que añade AIProviderUsageWizard.default_get.
FIGURE_KEYS = ('prompt_tokens', 'completion_tokens', 'total_tokens', 'cost_display')
ACTION_FIELDS = ['code', 'label', 'danger', 'active', 'group_ids', 'preview_method',
                 'apply_method', 'model_id', 'write_date']
# fields_get: existe en todo modelo (pasa _resolve_method), es @api.model, sin
# argumentos obligatorios y solo lee. La acción queda archivada: _get no la ve.
HARMLESS_METHOD = 'fields_get'
ALL = {'context': {'active_test': False}}

# Contraseñas de esta ejecución: nada de lo que se imprime o se guarda las lleva.
_SECRETS = []


class Parada(Exception):
    """Fin con código 2: precondición, conexión, autenticación o estado."""


def _safe(text):
    text = str(text)
    for secret in _SECRETS:
        text = text.replace(secret, '***')
    return text


def _out(text=''):
    print(_safe(text))
    sys.stdout.flush()


def _config():
    url = os.environ.get('E4P_URL', '').strip().rstrip('/')
    db = os.environ.get('E4P_DB', '').strip()
    if not url or not db:
        raise Parada('faltan E4P_URL o E4P_DB')
    return {
        'url': url,
        'db': db,
        'state': os.path.expanduser(os.environ.get('E4P_STATE') or DEFAULT_STATE),
        'admin': os.environ.get('E4P_ADMIN') or 'admin',
        'interno': os.environ.get('E4P_INTERNO') or 'demo',
        'aiadmin': os.environ.get('E4P_AIADMIN') or 'e1p_aiadmin',
    }


def _load(cfg):
    try:
        with open(cfg['state']) as fh:
            state = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as err:
        raise Parada('no se puede leer el estado %s: %s' % (cfg['state'], err)) from None
    if not isinstance(state, dict):
        raise Parada('el estado %s no es un objeto JSON' % cfg['state'])
    for key in ('url', 'db'):
        if state.get(key) and state[key] != cfg[key]:
            raise Parada('el estado %s es de otro servidor o BD (%s: %s)'
                         % (cfg['state'], key, state[key]))
    return state


def _save(cfg, state):
    path = cfg['state']
    folder = os.path.dirname(path) or '.'
    if not os.path.isdir(folder):
        os.makedirs(folder, mode=0o700)
        os.chmod(folder, 0o700)
    state.update({'url': cfg['url'], 'db': cfg['db']})
    tmp = path + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _retrying(func, *args):
    """Llama a func; ante un 503 reintenta hasta RETRIES veces. Lo demás no."""
    attempt = 0
    while True:
        try:
            return func(*args)
        except xmlrpc.client.ProtocolError as err:
            if err.errcode != 503:
                raise Parada('el servidor respondió HTTP %s' % err.errcode) from None
            if attempt >= RETRIES:
                raise Parada(
                    'el servidor sigue con HTTP 503 tras %d reintentos' % RETRIES) from None
            attempt += 1
            _out('  HTTP 503: reintento %d de %d en %s s' % (attempt, RETRIES, WAIT))
            time.sleep(WAIT)
        except (OSError, http.client.HTTPException, xmlrpc.client.ResponseError,
                ExpatError) as err:
            raise Parada(
                'sin conexión con el servidor: %s' % err.__class__.__name__) from None


def _line(code, text):
    """Primera línea del mensaje de un Fault. Con faultCode 1 llega la traza
    entera: la línea útil es la última (tipo y mensaje de la excepción)."""
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    if not lines:
        return ''
    line = lines[0]
    if code == FAULT_OTHER and line.startswith('Traceback'):
        line = lines[-1]
    return _safe(line)[:160]


class Usuario:
    def __init__(self, cfg, login):
        self.cfg = cfg
        self.login = login
        password = getpass.getpass('Contraseña de %s: ' % login)
        # Solo las de 8 o más caracteres: tapar una corta (p. ej. «admin») cambiaría
        # otras palabras de la salida y delataría la contraseña.
        if len(password) >= 8:
            _SECRETS.append(password)
        self._password = password
        common = xmlrpc.client.ServerProxy(cfg['url'] + '/xmlrpc/2/common')
        try:
            uid = _retrying(common.authenticate, cfg['db'], login, password, {})
        except xmlrpc.client.Fault as fault:
            raise Parada('no se pudo entrar como %s: %s'
                         % (login, _line(fault.faultCode, fault.faultString))) from None
        if not uid:
            raise Parada('no se pudo entrar como %s (usuario o contraseña)' % login)
        self.uid = uid
        self._models = xmlrpc.client.ServerProxy(
            cfg['url'] + '/xmlrpc/2/object', allow_none=True)

    def call(self, model, method, args, kwargs=None):
        """('ok', valor) o ('fault', faultCode, faultString)."""
        try:
            return ('ok', _retrying(
                self._models.execute_kw, self.cfg['db'], self.uid, self._password,
                model, method, args, kwargs or {}))
        except xmlrpc.client.Fault as fault:
            if fault.faultCode == FAULT_DENIED:
                raise Parada('el servidor rechazó la sesión de %s (AccessDenied)'
                             % self.login) from None
            return ('fault', fault.faultCode, fault.faultString)


def _need(res, what):
    if res[0] != 'ok':
        raise Parada('%s: %s' % (what, _line(res[1], res[2])))
    return res[1]


def _record(results, case, who, expected, ok, detail):
    results.append((case, who, expected, 'OK' if ok else 'FALLO', _safe(detail)))
    _out('%-8s %-12s esperado: %-34s -> %s: %s'
         % (case, who, expected, results[-1][3], results[-1][4]))


def _by_patch(res, messages, patch):
    """(ok, detalle) de un rechazo que debe dar el parche con su mensaje propio."""
    if res[0] == 'ok':
        return False, 'respondió sin error: el parche %s no está' % patch
    code, text = res[1], res[2]
    line = _line(code, text)
    if code == FAULT_ACCESS:
        if any(msg in text for msg in messages):
            return True, 'AccessError: ' + line
        return False, 'rechazado, pero no por el parche: ' + line
    if code == FAULT_OTHER and 'cannot marshal None' in text:
        return False, 'se ejecutó (devolvió None): el parche %s no está' % patch
    if code == FAULT_USER:
        return False, 'UserError: ' + line
    return False, 'faultCode %s: %s' % (code, line)


def _has_figures(value):
    text = json.dumps(value, default=str)
    return [key for key in FIGURE_KEYS if key in text]


def _no_figures(res):
    """Asistente de uso para quien no es AI Administrator: AccessError (la ACL
    del core, check_access_rights) y ninguna cifra en la respuesta."""
    if res[0] == 'ok':
        if _has_figures(res[1]):
            return False, 'devolvió las cifras: el parche 33 no está'
        return False, 'respondió sin error'
    if res[1] == FAULT_ACCESS:
        return True, 'AccessError (ACL): ' + _line(res[1], res[2])
    return False, 'faultCode %s: %s' % (res[1], _line(res[1], res[2]))


def _sql(admin_uid, t0):
    since = (datetime.datetime.strptime(t0, '%Y-%m-%d %H:%M:%S')
             - datetime.timedelta(seconds=T0_MARGIN)).strftime('%Y-%m-%d %H:%M:%S')
    return (
        "-- P-30: debe dar 0 filas. t0 (UTC) = %s; se mira desde t0 - %d s.\n"
        "-- create_date está en UTC sin zona. Los log_* de P-30 escriben en endpoint\n"
        "-- capability_skipped, llm_orchestration, llm_response y %s.\n"
        "SELECT id, create_date, user_id, create_uid, endpoint, primitive,\n"
        "       provider_id, total_tokens, cost_usd, left(result_summary, 60) AS resumen\n"
        "  FROM ai_log\n"
        " WHERE endpoint = '%s'\n"
        "    OR (user_id = %d AND create_date >= '%s')\n"
        " ORDER BY id;"
    ) % (t0, T0_MARGIN, LOG_ENDPOINT, LOG_ENDPOINT, int(admin_uid), since)


def preparar(cfg, state, results):
    admin = Usuario(cfg, cfg['admin'])
    found = _need(admin.call('ai.trusted.action', 'search',
                             [[('code', '=', CODE)]], ALL), 'buscar %s' % CODE)
    if found:
        action_id = found[0]
        _out('%s ya existe (ai.trusted.action %s): se reutiliza' % (CODE, action_id))
    else:
        model = _need(admin.call('ir.model', 'search', [[('model', '=', 'res.partner')]]),
                      'buscar el modelo res.partner')
        group = _need(admin.call('ir.model.data', 'search_read', [[
            ('module', '=', 'base'), ('name', '=', 'group_system'),
            ('model', '=', 'res.groups')]], {'fields': ['res_id']}),
            'buscar base.group_system')
        if not model or not group:
            raise Parada('no se encuentran res.partner o base.group_system')
        res = admin.call('ai.trusted.action', 'create', [{
            'code': CODE,
            'label': 'Seges E4p (pruebas de staging)',
            'model_id': model[0],
            'preview_method': HARMLESS_METHOD,
            'apply_method': HARMLESS_METHOD,
            'group_ids': [(6, 0, [group[0]['res_id']])],
            'active': False,
        }])
        action_id = _need(res, 'crear %s' % CODE)
        state['accion_id'] = action_id
        _save(cfg, state)
        _out('%s creada (ai.trusted.action %s), archivada y solo para Ajustes'
             % (CODE, action_id))
    state['accion_id'] = action_id
    _save(cfg, state)
    _out('Estado: %s' % cfg['state'])
    return 0


def _precondition(interno, aiadmin):
    wanted = [(interno, 'base.group_user', True)]
    wanted += [(interno, group, False) for group in AI_GROUPS]
    wanted += [(aiadmin, 'pns_ai_mcp.group_ai_admin', True),
               (aiadmin, 'base.group_system', False)]
    wrong = []
    for user, group, expected in wanted:
        res = user.call('res.users', 'has_group', [group])
        if res[0] != 'ok':
            wrong.append('%s, %s: %s' % (user.login, group, _line(res[1], res[2])))
        elif bool(res[1]) != expected:
            wrong.append('%s %s %s' % (user.login, 'no tiene' if expected else 'tiene', group))
    if wrong:
        raise Parada('precondición de grupos (D3): ' + '; '.join(wrong))
    _out('Precondición (D3): %s es interno sin grupos de IA; %s es AI Administrator '
         'sin Ajustes' % (interno.login, aiadmin.login))


def _p30(results, interno, admin):
    _out('== P-30 (parche 30): log_* a nombre de admin (uid %s)' % admin.uid)
    for n, (method, args, kwargs) in enumerate(LOG_CALLS, 1):
        res = interno.call('ai.execution.engine', method, [[]] + args,
                           dict(kwargs, user_id=admin.uid))
        ok, detail = _by_patch(res, MSG_30, 30)
        _record(results, 'P-30.%d' % n, interno.login,
                'AccessError (30) %s' % method, ok, detail)


def _p31(results, interno):
    _out('== P-31 (parche 31): chat_completion')
    res = interno.call('ai.execution.engine', 'chat_completion',
                       [[], MISSING_AGENT, MESSAGES])
    ok, detail = _by_patch(res, MSG_31, 31)
    if res[0] == 'fault' and res[1] == FAULT_USER:
        # resolve_inference_agent_code: el agente no existe y nada lo ha parado antes.
        detail = 'UserError, el parche 31 no está: ' + _line(res[1], res[2])
    _record(results, 'P-31', interno.login, 'AccessError (31)', ok, detail)


def _p33(cfg, state, results, interno, admin):
    _out('== P-33 (parche 33): cifras del mes del proveedor')
    found = _need(admin.call('ai.provider', 'search', [[('active', '=', True)]],
                             {'limit': 1, 'order': 'id'}), 'buscar un ai.provider activo')
    cases = [
        ('P-33.1', interno.login, 'AttributeError (no existe)'),
        ('P-33.2', interno.login, 'AccessError (método privado)'),
        ('P-33.3', interno.login, 'AccessError y sin cifras'),
        ('P-33.4', interno.login, 'AccessError y sin cifras'),
        ('P-33.5', admin.login, 'ok y llegan las cifras'),
    ]
    if not found:
        for case, who, expected in cases:
            _record(results, case, who, expected, False, 'no hay ningún ai.provider activo')
        return
    provider_id = found[0]
    state['proveedor_id'] = provider_id
    _save(cfg, state)
    _out('ai.provider %s' % provider_id)
    ctx = {'context': {'default_provider_id': provider_id}}

    res = interno.call('ai.provider', 'month_usage', [[provider_id]])
    if res[0] == 'ok':
        ok, detail = False, 'existe y responde: el parche 33 no está'
    else:
        ok = (res[1] == FAULT_OTHER and 'AttributeError' in res[2]
              and 'month_usage' in res[2])
        detail = _line(res[1], res[2])
    _record(results, *cases[0], ok, detail)

    res = interno.call('ai.provider', '_month_usage', [[provider_id]])
    if res[0] == 'ok':
        ok, detail = False, 'respondió sin error'
    else:
        ok = res[1] == FAULT_ACCESS and '_month_usage' in res[2]
        detail = _line(res[1], res[2])
    _record(results, *cases[1], ok, detail)

    res = interno.call(WIZARD, 'default_get', [WIZARD_FIELDS], ctx)
    _record(results, cases[2][0], cases[2][1], 'default_get: ' + cases[2][2],
            *_no_figures(res))
    res = interno.call(WIZARD, 'onchange', [[], {}, [], ONCHANGE_SPEC], ctx)
    _record(results, cases[3][0], cases[3][1], 'onchange: ' + cases[3][2],
            *_no_figures(res))

    # Control: solo se dice qué claves llegan, sin sus valores.
    res = admin.call(WIZARD, 'default_get', [WIZARD_FIELDS], ctx)
    if res[0] != 'ok':
        ok, detail = False, 'admin no ve las cifras: ' + _line(res[1], res[2])
    else:
        keys = [key for key in FIGURE_KEYS if isinstance(res[1], dict) and key in res[1]]
        ok = len(keys) == len(FIGURE_KEYS)
        detail = 'llegan las claves: %s' % (', '.join(keys) or 'ninguna')
    _record(results, cases[4][0], cases[4][1], 'default_get: ' + cases[4][2], ok, detail)


def _keep_created(cfg, state, res):
    """Ids que devolvió un create o un copy que debía rechazarse: al estado ya."""
    ids = res[1] if isinstance(res[1], list) else [res[1]]
    ids = [i for i in ids if isinstance(i, int) and not isinstance(i, bool)]
    created = state.setdefault('creados', [])
    created.extend(i for i in ids if i not in created)
    _save(cfg, state)
    return ids


def _p32(cfg, state, results, aiadmin, admin):
    _out('== P-32 (parche 32): AI Administrator sin Ajustes sobre %s' % CODE)
    action_id = state['accion_id']
    cases = [
        ('P-32.1', 'write del label'),
        ('P-32.2', 'create de %s.b' % CODE),
        ('P-32.3', 'copy'),
        ('P-32.4', 'unlink'),
    ]
    before = admin.call('ai.trusted.action', 'read', [[action_id], ACTION_FIELDS], ALL)
    if before[0] != 'ok' or not before[1]:
        why = ('no se pudo leer: ' + _line(before[1], before[2]) if before[0] != 'ok'
               else '%s (%s) no existe: ejecuta preparar' % (CODE, action_id))
        for case, what in cases:
            _record(results, case, aiadmin.login, 'AccessError (32) ' + what, False, why)
        _record(results, 'P-32.5', admin.login, 'sin cambios', False, why)
        return
    before = before[1][0]

    res = aiadmin.call('ai.trusted.action', 'write', [[action_id], {'label': before['label']}])
    _record(results, cases[0][0], aiadmin.login, 'AccessError (32) ' + cases[0][1],
            *_by_patch(res, MSG_32, 32))

    vals = {
        'code': CODE + '.b',
        'label': before['label'],
        'danger': before['danger'],
        'active': before['active'],
        'group_ids': [(6, 0, before['group_ids'])],
        'model_id': before['model_id'] and before['model_id'][0],
        'preview_method': before['preview_method'],
        'apply_method': before['apply_method'],
    }
    res = aiadmin.call('ai.trusted.action', 'create', [vals])
    ok, detail = _by_patch(res, MSG_32, 32)
    if res[0] == 'ok':
        detail = 'creó ai.trusted.action %s: el parche 32 no está' % _keep_created(cfg, state, res)
    _record(results, cases[1][0], aiadmin.login, 'AccessError (32) ' + cases[1][1], ok, detail)

    # Con otro code: el mismo chocaría con code_uniq y no discriminaría.
    res = aiadmin.call('ai.trusted.action', 'copy', [[action_id]],
                       {'default': {'code': CODE + '.copia'}})
    ok, detail = _by_patch(res, MSG_32, 32)
    if res[0] == 'ok':
        detail = 'copió en ai.trusted.action %s: el parche 32 no está' % _keep_created(
            cfg, state, res)
    _record(results, cases[2][0], aiadmin.login, 'AccessError (32) ' + cases[2][1], ok, detail)

    res = aiadmin.call('ai.trusted.action', 'unlink', [[action_id]])
    _record(results, cases[3][0], aiadmin.login, 'AccessError (32) ' + cases[3][1],
            *_by_patch(res, MSG_32, 32))

    after = admin.call('ai.trusted.action', 'read', [[action_id], ACTION_FIELDS], ALL)
    if after[0] != 'ok':
        ok, detail = False, 'no se pudo leer: ' + _line(after[1], after[2])
    elif not after[1]:
        ok, detail = False, '%s ya no existe: la borró %s' % (CODE, aiadmin.login)
    else:
        changed = [f for f in ACTION_FIELDS if after[1][0].get(f) != before.get(f)]
        ok = not changed
        detail = ('cambió: ' + ', '.join(changed)) if changed else 'igual (write_date incluido)'
    _record(results, 'P-32.5', admin.login, 'sin cambios', ok, detail)


def rpc(cfg, state, results):
    if not state.get('accion_id'):
        raise Parada('el estado %s no tiene %s: ejecuta antes preparar'
                     % (cfg['state'], CODE))
    interno = Usuario(cfg, cfg['interno'])
    aiadmin = Usuario(cfg, cfg['aiadmin'])
    _precondition(interno, aiadmin)
    admin = Usuario(cfg, cfg['admin'])
    t0 = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    state['t0'] = t0
    state['admin_uid'] = admin.uid
    _save(cfg, state)
    _out('t0 (UTC): %s' % t0)
    _p30(results, interno, admin)
    _out('Consulta de comprobación de P-30 (en la BD del staging, solo lectura):')
    _out(_sql(admin.uid, t0))
    _p31(results, interno)
    _p33(cfg, state, results, interno, admin)
    _p32(cfg, state, results, aiadmin, admin)
    return 1 if any(row[3] != 'OK' for row in results) else 0


def _report(cfg, state, results, stop):
    rows = [('Comprobación', 'Usuario', 'Esperado', 'Resultado', 'Detalle')] + results
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    table = ['  '.join(row[i].ljust(widths[i]) for i in range(4)) + '  ' + row[4]
             for row in rows]
    failed = sum(1 for row in results if row[3] != 'OK')
    lines = ['Pruebas de E4′ por XML-RPC · %s · BD %s · %s'
             % (cfg['url'], cfg['db'], datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
             't0 (UTC): %s' % state.get('t0', '-'), ''] + table + [
             '', '%d comprobaciones: %d OK, %d FALLO'
             % (len(results), len(results) - failed, failed)]
    if stop:
        lines.append('PARADA: %s' % stop)
    if state.get('t0') and state.get('admin_uid'):
        lines += ['', _sql(state['admin_uid'], state['t0'])]
    text = _safe('\n'.join(lines) + '\n')
    _out('')
    _out('\n'.join(lines[3:3 + len(table) + 2]))
    path = os.path.join(
        os.path.dirname(cfg['state']) or '.',
        'resultado_e4p_%s.txt' % datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as fh:
        fh.write(text)
    _out('Tabla copiada en %s' % path)


def limpiar(cfg, state, results):
    admin = Usuario(cfg, cfg['admin'])
    ids = set(_need(admin.call('ai.trusted.action', 'search',
                               [[('code', '=like', CODE + '%')]], ALL),
                    'buscar las acciones %s*' % CODE))
    known = [state.get('accion_id')] + list(state.get('creados') or [])
    known = [i for i in known if isinstance(i, int) and not isinstance(i, bool)]
    if known:
        # Los del estado que siguen existiendo: limpiar se puede repetir.
        ids.update(_need(admin.call('ai.trusted.action', 'search',
                                    [[('id', 'in', known)]], ALL),
                         'buscar los ids del estado'))
    ids = sorted(ids)
    if ids:
        _need(admin.call('ai.trusted.action', 'unlink', [ids]), 'borrar %s' % ids)
    _out('Acciones de confianza borradas: %d %s' % (len(ids), ids if ids else ''))
    state.pop('accion_id', None)
    state['creados'] = []
    if os.path.exists(cfg['state']):
        _save(cfg, state)
        _out('Queda el archivo de estado: %s' % cfg['state'])
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    steps = {'preparar': preparar, 'rpc': rpc, 'limpiar': limpiar}
    if len(argv) != 1 or argv[0] not in steps:
        _out(__doc__)
        return 2
    del _SECRETS[:]
    results = []
    cfg, state, stop = None, {}, None
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(TIMEOUT)
    try:
        cfg = _config()
        state = _load(cfg)
        code = steps[argv[0]](cfg, state, results)
    except Parada as err:
        stop = _safe(err)
        _out('PARADA: %s' % stop)
        code = 2
    finally:
        socket.setdefaulttimeout(old_timeout)
    if argv[0] == 'rpc' and results:
        _report(cfg, state, results, stop)
    return code


if __name__ == '__main__':
    sys.exit(main())
