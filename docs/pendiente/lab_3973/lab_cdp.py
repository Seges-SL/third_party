#!/usr/bin/env python3
"""Laboratorio de lab_pns_ai_3973 con Chrome headless (--remote-debugging-pipe).

Solo biblioteca estándar: sin Node, sin websocket-client, sin instalar nada.

Órdenes:
  c            Comprobación C sobre un log leído por la entrada estándar
               (la misma lógica que lab_procedimiento_3973.md).
  navegar      Entra como LAB_LOGIN/LAB_PASSWORD por /web/login?db=lab_pns_ai_3973_14,
               hace C sobre el log del servidor, comprueba que la sesión es de
               lab_pns_ai_3973_14 y visita las rutas dadas. Por ruta: imágenes
               pintadas en el marco srcdoc, «Refused» de CSP por directiva
               (consola de Chrome), errores de JS y una captura. Bloquea
               cualquier petición a /web/database/*.
  autoprueba   Lo mismo contra un servidor simulado en 127.0.0.1 (sin Odoo),
               con resultados esperados. Sirve para validar el script en el equipo.

No imprime contenido de las páginas ni del log: solo nombres de BD, recuentos y
nombres de archivo. Los textos de los errores de JS van a <salida>/detalle.txt,
que es local y no se copia a la documentación.

Códigos de salida: 0 todo como se espera; 1 hay incidencias; 2 abortado
(C con otra BD, sesión de otra BD o error de Chrome).
"""
import argparse
import base64
import collections
import fcntl
import html
import io
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

BD = 'lab_pns_ai_3973_14'
BASE = 'http://localhost:8169'
LAB = os.path.expanduser('~/GitHub/lab_pns_ai_3973')
CHROME = '/usr/bin/google-chrome'
PERMITIDAS = {'?', BD}
# Rutas que el navegador no puede pedir nunca (selector y gestor de BD).
BLOQUEO = ['*/web/database/*']
ESPERA_PINTADO = 2.5  # segundos tras la carga para que el diseño pinte

MEDIR_JS = r"""(() => {
  const im = Array.from(document.images);
  const m = document.querySelector('meta[http-equiv="Content-Security-Policy" i]');
  return {
    total: im.length,
    pintadas: im.filter(i => i.complete && i.naturalWidth > 0).length,
    rotas: im.filter(i => i.complete && i.naturalWidth === 0).length,
    meta_csp: !!m,
    meta_csp_primera: !!m && document.head && document.head.children[1] === m,
    modo: document.compatMode,
  };
})()"""
# Chrome 153: «Loading the image '…' violates the following Content Security
# Policy directive: "img-src …". The action has been blocked.» Versiones
# anteriores: «Refused to load … because it violates the following …».
RE_REFUSED = re.compile(r'violates the following Content Security Policy directive: "([a-z-]+)')
RE_CSP_SIN_DIRECTIVA = re.compile(r"violates the document's Content Security Policy")


# --------------------------------------------------------------------------
# Comprobación C (idéntica a la del procedimiento)
# --------------------------------------------------------------------------
PAT_C = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ \S+ (\S+) (\S+): (.*)")


def comprobacion_c(lineas_log):
    lineas = collections.Counter()
    crons = collections.Counter()
    for linea in lineas_log:
        m = PAT_C.search(linea)
        if not m:
            continue
        lineas[m.group(1)] += 1
        if m.group(2) == "odoo.addons.base.models.ir_cron" and m.group(3).startswith("Starting job"):
            crons[m.group(1)] += 1
    print("BD con líneas:", ", ".join("%s (%d)" % kv for kv in sorted(lineas.items())) or "ninguna")
    print("BD con Starting job:", ", ".join("%s (%d)" % kv for kv in sorted(crons.items())) or "ninguna")
    ok = set(lineas) <= PERMITIDAS and set(crons) <= {BD}
    print("C:", "OK" if ok else "OTRA BD (parar: «Si aparece otra BD»)")
    return ok


def c_en_vivo():
    """C sobre `odoo-dev 14 log all`, ejecutado desde la carpeta del laboratorio."""
    salida = subprocess.run(
        ['odoo-dev', '14', 'log', 'all'], cwd=LAB,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    ).stdout
    return comprobacion_c(io.StringIO(salida.decode('utf-8', 'replace')))


# --------------------------------------------------------------------------
# Chrome por tubería
# --------------------------------------------------------------------------
class ErrorCDP(Exception):
    pass


class Chrome:
    """Chrome headless hablando CDP por los descriptores 3 (lee) y 4 (escribe).

    Mensajes JSON terminados en \\0. Los extremos del hijo se suben por encima
    de 10 y se colocan en 3 y 4 justo antes del exec; los demás descriptores de
    Python no son heredables (PEP 446), así que no se filtra nada más.
    """

    def __init__(self, perfil, salida):
        r_hijo, self.wr = os.pipe()
        self.rd, w_hijo = os.pipe()
        a = fcntl.fcntl(r_hijo, fcntl.F_DUPFD, 10)
        b = fcntl.fcntl(w_hijo, fcntl.F_DUPFD, 10)
        os.close(r_hijo)
        os.close(w_hijo)

        def en_hijo():
            os.dup2(a, 3)
            os.dup2(b, 4)

        args = [
            CHROME, '--headless=new', '--remote-debugging-pipe',
            '--user-data-dir=' + perfil, '--no-first-run',
            '--no-default-browser-check', '--disable-extensions',
            '--disable-sync', '--disable-background-networking',
            '--disable-component-update', '--disable-default-apps',
            '--window-size=1366,900', 'about:blank',
        ]
        if os.geteuid() == 0:
            args.insert(1, '--no-sandbox')
        self.err = open(os.path.join(salida, 'chrome_stderr.txt'), 'wb')
        self.proc = subprocess.Popen(
            args, preexec_fn=en_hijo, close_fds=False,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=self.err,
        )
        os.close(a)
        os.close(b)
        self.buf = b''
        self.n = 0
        self.respuestas = {}
        self.pagina = None
        self.sesiones = []
        self.medida = None
        self.cargas = 0
        self.descargas = {}
        self.bloqueadas = 0
        self.detalle = open(os.path.join(salida, 'detalle.txt'), 'a', encoding='utf-8')

    # -- transporte --------------------------------------------------------
    def _enviar(self, metodo, params=None, sesion=None):
        self.n += 1
        m = {'id': self.n, 'method': metodo, 'params': params or {}}
        if sesion:
            m['sessionId'] = sesion
        datos = json.dumps(m).encode() + b'\0'
        while datos:
            datos = datos[os.write(self.wr, datos):]
        return self.n

    def _leer(self, espera):
        listos, _, _ = select.select([self.rd], [], [], max(espera, 0))
        if not listos:
            return
        trozo = os.read(self.rd, 1 << 20)
        if not trozo:
            raise ErrorCDP('Chrome cerró la tubería (ver chrome_stderr.txt)')
        self.buf += trozo
        while b'\0' in self.buf:
            msg, self.buf = self.buf.split(b'\0', 1)
            m = json.loads(msg)
            if 'id' in m:
                self.respuestas[m['id']] = m
            else:
                self._evento(m)

    def llamar(self, metodo, params=None, sesion=None, espera=30):
        i = self._enviar(metodo, params, sesion)
        fin = time.time() + espera
        while i not in self.respuestas:
            if time.time() > fin:
                raise ErrorCDP('sin respuesta: ' + metodo)
            self._leer(fin - time.time())
        r = self.respuestas.pop(i)
        if 'error' in r:
            raise ErrorCDP('%s: %s' % (metodo, r['error'].get('message')))
        return r.get('result', {})

    def esperar(self, condicion, espera):
        fin = time.time() + espera
        while not condicion():
            if time.time() > fin:
                return False
            self._leer(min(0.2, fin - time.time()))
        return True

    def bombear(self, segundos):
        fin = time.time() + segundos
        while time.time() < fin:
            self._leer(fin - time.time())

    # -- eventos -----------------------------------------------------------
    def _preparar(self, sesion, esperar_respuesta):
        # Chrome aísla en su propio proceso los iframes con sandbox (el srcdoc
        # del lienzo): llega como destino hijo, detenido hasta
        # runIfWaitingForDebugger, que se envía el último para que Log y Fetch
        # ya estén activos cuando corra el diseño.
        enviar = (lambda m, p=None: self.llamar(m, p, sesion)) if esperar_respuesta \
            else (lambda m, p=None: self._enviar(m, p, sesion))
        enviar('Page.enable')
        enviar('Runtime.enable')
        enviar('Log.enable')
        enviar('Fetch.enable', {'patterns': [{'urlPattern': p} for p in BLOQUEO]})
        enviar('Target.setAutoAttach', {
            'autoAttach': True, 'waitForDebuggerOnStart': True, 'flatten': True})
        enviar('Runtime.runIfWaitingForDebugger')

    def _anotar(self, clave, texto=None):
        if self.medida is not None:
            self.medida[clave] += 1
        if texto:
            self.detalle.write('[%s] %s: %s\n' % (
                self.medida_ruta if self.medida is not None else '-', clave, texto))

    def _evento(self, m):
        metodo, p, s = m['method'], m.get('params', {}), m.get('sessionId')
        if metodo == 'Target.attachedToTarget':
            if p.get('targetInfo', {}).get('type') in ('iframe', 'page'):
                self.sesiones.append(p['sessionId'])
                self._preparar(p['sessionId'], esperar_respuesta=False)
        elif metodo == 'Target.detachedFromTarget':
            if p.get('sessionId') in self.sesiones:
                self.sesiones.remove(p['sessionId'])
        elif metodo == 'Fetch.requestPaused':
            self.bloqueadas += 1
            self._anotar('bloqueadas_por_guardia')
            self._enviar('Fetch.failRequest',
                         {'requestId': p['requestId'], 'errorReason': 'BlockedByClient'}, s)
        elif metodo == 'Log.entryAdded':
            e = p.get('entry', {})
            r = RE_REFUSED.search(e.get('text', ''))
            if r:
                self._anotar('refused:' + r.group(1))
            elif RE_CSP_SIN_DIRECTIVA.search(e.get('text', '')):
                self._anotar('csp_repetido', e.get('text', '')[:200])
            elif e.get('source') == 'network':
                self._anotar('recursos_http', e.get('text', '')[:300] + ' ' + e.get('url', '')[:200])
            elif e.get('level') == 'error':
                self._anotar('errores_log', e.get('text', '')[:500])
        elif metodo == 'Runtime.consoleAPICalled':
            args = p.get('args') or [{}]
            v = str(args[0].get('value', ''))
            if p.get('type') == 'error':
                self._anotar('errores_consola', v[:500])
        elif metodo == 'Runtime.exceptionThrown':
            d = p.get('exceptionDetails', {})
            self._anotar('excepciones_js', (d.get('exception', {}).get('description')
                                            or d.get('text', ''))[:500])
        elif metodo == 'Page.loadEventFired' and s == self.pagina:
            self.cargas += 1
        elif metodo == 'Browser.downloadWillBegin':
            self.descargas[p['guid']] = None
        elif metodo == 'Browser.downloadProgress' and p.get('state') in ('completed', 'canceled'):
            self.descargas[p['guid']] = p['state']

    # -- arranque y cierre -------------------------------------------------
    def abrir_pagina(self, descargas_dir):
        self.llamar('Browser.setDownloadBehavior', {
            'behavior': 'allowAndName', 'downloadPath': descargas_dir, 'eventsEnabled': True})
        t = self.llamar('Target.createTarget', {'url': 'about:blank'})['targetId']
        self.pagina = self.llamar('Target.attachToTarget',
                                  {'targetId': t, 'flatten': True})['sessionId']
        self._preparar(self.pagina, esperar_respuesta=True)

    def cerrar(self):
        try:
            self._enviar('Browser.close')
            self.proc.wait(10)
        except Exception:
            self.proc.kill()
        self.detalle.close()
        self.err.close()

    # -- acciones ----------------------------------------------------------
    def nueva_medida(self, ruta):
        self.medida = collections.Counter()
        self.medida_ruta = ruta

    def ir(self, url, espera=60):
        self.cargas = 0
        r = self.llamar('Page.navigate', {'url': url}, self.pagina)
        if r.get('errorText'):
            return r['errorText']
        if not self.esperar(lambda: self.cargas >= 1, espera):
            return 'sin evento load en %d s' % espera
        return None

    def evaluar(self, expr, sesion=None, contexto=None, promesa=False):
        p = {'expression': expr, 'returnByValue': True, 'awaitPromise': promesa}
        if contexto:
            p['contextId'] = contexto
        r = self.llamar('Runtime.evaluate', p, sesion or self.pagina)
        if 'exceptionDetails' in r:
            raise ErrorCDP('evaluate: ' + r['exceptionDetails'].get('text', ''))
        return r['result'].get('value')

    def medir_marcos(self, incluir_principal=False):
        """Imágenes y CSP en cada marco srcdoc (o en el documento principal)."""
        vistos, res = set(), []
        for s in [self.pagina] + list(self.sesiones):
            try:
                arbol = self.llamar('Page.getFrameTree', None, s)['frameTree']
            except ErrorCDP:
                continue
            pila = [(arbol, True)]
            while pila:
                nodo, raiz = pila.pop()
                f = nodo['frame']
                es_principal = raiz and s == self.pagina
                if f['id'] not in vistos and (
                        f.get('url') == 'about:srcdoc' or (incluir_principal and es_principal)):
                    vistos.add(f['id'])
                    ctx = self.llamar('Page.createIsolatedWorld', {
                        'frameId': f['id'], 'worldName': 'seges_lab'}, s)['executionContextId']
                    res.append(self.evaluar(MEDIR_JS, s, ctx))
                pila.extend((h, False) for h in nodo.get('childFrames', []))
        return res

    def captura(self, ruta_png):
        datos = self.llamar('Page.captureScreenshot', {'format': 'png'}, self.pagina)['data']
        with open(ruta_png, 'wb') as f:
            f.write(base64.b64decode(datos))


# --------------------------------------------------------------------------
# Laboratorio
# --------------------------------------------------------------------------
def esperar_servidor(base, espera=120):
    """version_info es auth='none' y no carga ninguna BD."""
    peticion = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {}}).encode()
    fin = time.time() + espera
    while time.time() < fin:
        try:
            req = urllib.request.Request(base + '/web/webclient/version_info', peticion,
                                         {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(2)
    return False


def comprobar_ruta(ruta):
    if not ruta.startswith('/') or ruta.startswith('//'):
        raise SystemExit('ruta no válida (debe empezar por una sola /): %s' % ruta)
    if '/web/database' in ruta:
        raise SystemExit('ruta prohibida: %s' % ruta)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(ruta).query)
    if any(v != BD for v in q.get('db', [])):
        raise SystemExit('ruta con otra BD: %s' % ruta)


def nombre_archivo(ruta):
    return re.sub(r'[^A-Za-z0-9]+', '_', ruta).strip('_') or 'raiz'


def resumir(ruta, error, marcos, medida, captura):
    incid = []
    print('\n== %s' % ruta)
    if error:
        print('  carga: %s' % error)
        incid.append('carga')
    else:
        print('  carga: ok')
    for i, m in enumerate(marcos, 1):
        print('  marco %d: imágenes %d/%d pintadas, %d rotas; <meta> CSP %s%s; %s' % (
            i, m['pintadas'], m['total'], m['rotas'], 'sí' if m['meta_csp'] else 'NO',
            ' (2.º hijo de <head>)' if m['meta_csp_primera'] else '', m['modo']))
        if m['rotas'] or not m['meta_csp'] or m['modo'] != 'CSS1Compat':
            incid.append('marco %d' % i)
    if not marcos:
        print('  marco: ninguno medido')
        incid.append('sin marco')
    refused = sorted((k.split(':', 1)[1], v) for k, v in medida.items() if k.startswith('refused:'))
    print('  Refused (consola): %s' % (', '.join('%s %d' % kv for kv in refused) or 'ninguno'))
    if medida['recursos_http']:
        print('  recursos con error HTTP (informativo): %d' % medida['recursos_http'])
    errores = medida['errores_log'] + medida['errores_consola'] + medida['excepciones_js']
    print('  errores de JS: %d (textos en detalle.txt)' % errores)
    if medida['bloqueadas_por_guardia']:
        print('  peticiones a /web/database bloqueadas: %d' % medida['bloqueadas_por_guardia'])
    if captura:
        print('  captura: %s' % os.path.basename(captura))
    if refused or medida['csp_repetido']:
        incid.append('csp')
    if errores:
        incid.append('js')
    if medida['bloqueadas_por_guardia']:
        incid.append('guardia')
    return incid


def entrar(ch, base, login, clave):
    err = ch.ir(base + '/web/login?db=' + BD)
    if err:
        raise ErrorCDP('login: ' + err)
    js = (
        "(() => { const f = document.querySelector('form.oe_login_form');"
        " if (!f) return 'sin-formulario';"
        " f.querySelector('input[name=login]').value = %s;"
        " f.querySelector('input[name=password]').value = %s;"
        " f.submit(); return 'ok'; })()" % (json.dumps(login), json.dumps(clave)))
    ch.cargas = 0
    if ch.evaluar(js) != 'ok':
        raise ErrorCDP('login: no está el formulario de /web/login')
    if not ch.esperar(lambda: ch.cargas >= 1, 90):
        raise ErrorCDP('login: la página tras el envío no cargó')
    ruta = ch.evaluar('location.pathname')
    if not ruta.startswith('/web') or ruta.startswith('/web/login'):
        raise ErrorCDP('login: no entró (ruta %s)' % ruta)
    info = ch.evaluar(
        "fetch('/web/session/get_session_info', {method: 'POST',"
        " headers: {'Content-Type': 'application/json'},"
        " body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {}})})"
        ".then(r => r.json()).then(j => ({db: j.result && j.result.db,"
        " uid: j.result && j.result.uid}))", promesa=True)
    return info


def navegar(args, base=BASE, c_func=c_en_vivo, login=None, clave=None):
    login = login or os.environ.get('LAB_LOGIN')
    clave = clave or os.environ.get('LAB_PASSWORD')
    if not login or not clave:
        raise SystemExit('Faltan LAB_LOGIN y LAB_PASSWORD en el entorno.')
    for r in args.rutas + args.descarga:
        comprobar_ruta(r)
    os.makedirs(args.salida, exist_ok=True)
    perfil = tempfile.mkdtemp(prefix='lab3973-chrome-')
    descargas = tempfile.mkdtemp(prefix='lab3973-descargas-')
    print('Esperando al servidor…')
    if not esperar_servidor(base):
        print('El servidor no responde en %s' % base)
        return 2
    ch = Chrome(perfil, args.salida)
    incidencias = []
    try:
        ch.abrir_pagina(descargas)
        ch.nueva_medida('login')
        info = entrar(ch, base, login, clave)
        print('Sesión: BD %s, uid %s' % (info.get('db'), info.get('uid')))
        if info.get('db') != BD:
            print('ABORTADO: la sesión no es de %s' % BD)
            return 2
        print('\nComprobación C tras la entrada:')
        if not c_func():
            return 2
        for ruta in args.rutas:
            ch.nueva_medida(ruta)
            err = ch.ir(base + ruta)
            ch.bombear(ESPERA_PINTADO)
            marcos = [] if err else ch.medir_marcos()
            png = os.path.join(args.salida, nombre_archivo(ruta) + '.png')
            ch.captura(png)
            incidencias += [(ruta, i) for i in resumir(ruta, err, marcos, ch.medida, png)]
        for ruta in args.descarga:
            ch.nueva_medida(ruta)
            ch.descargas.clear()
            ch.llamar('Page.navigate', {'url': base + ruta}, ch.pagina)
            ok = ch.esperar(lambda: ch.descargas and all(ch.descargas.values()), 30)
            guid = next(iter(ch.descargas), None)
            archivo = os.path.join(descargas, guid) if guid else None
            if not ok or ch.descargas.get(guid) != 'completed' or not os.path.exists(archivo):
                print('\n== %s\n  descarga: NO completada' % ruta)
                incidencias.append((ruta, 'descarga'))
                continue
            destino = os.path.join(args.salida, nombre_archivo(ruta) + '.html')
            shutil.copyfile(archivo, destino)
            ch.nueva_medida(ruta + ' (desde el disco)')
            err = ch.ir('file://' + destino)
            ch.bombear(ESPERA_PINTADO)
            marcos = [] if err else ch.medir_marcos(incluir_principal=True)
            png = os.path.join(args.salida, nombre_archivo(ruta) + '.png')
            ch.captura(png)
            incidencias += [(ruta, i) for i in resumir(
                ruta + ' (desde el disco: %s)' % os.path.basename(destino),
                err, marcos, ch.medida, png)]
    except ErrorCDP as e:
        print('ABORTADO: %s' % e)
        return 2
    finally:
        ch.cerrar()
        shutil.rmtree(perfil, ignore_errors=True)
        shutil.rmtree(descargas, ignore_errors=True)
    print('\nResultado: %s' % ('sin incidencias' if not incidencias else
                               'incidencias: ' + '; '.join('%s → %s' % x for x in incidencias)))
    print('Peticiones a /web/database bloqueadas en total: %d' % ch.bloqueadas)
    return 1 if incidencias else 0


# --------------------------------------------------------------------------
# Autoprueba (servidor simulado, sin Odoo)
# --------------------------------------------------------------------------
PNG = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
CSP_FAB = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
           "img-src 'self' data: blob:; font-src data:; connect-src 'self'; "
           "form-action 'none'; base-uri 'none'; frame-ancestors 'self'")
PREFIJO = ('<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
           'content="default-src \'none\'; script-src \'unsafe-inline\'; '
           'style-src \'unsafe-inline\'; img-src data: blob:; font-src data:; '
           'connect-src \'none\'; form-action \'none\'; base-uri \'none\'; '
           'frame-src \'none\'; object-src \'none\'; worker-src \'none\'">')
IMG = '<img src="data:image/png;base64,%s" width="20" height="20">' % PNG
DISENO_LIMPIO = '<html><head><title>t</title></head><body><h1>Prueba</h1>%s%s</body></html>' % (IMG, IMG)
DISENO_SELF = ('<html><head></head><body>%s<img src="/web/image/1">'
               '<script>fetch("/x").catch(function(){});</script></body></html>' % IMG)
LOG_BUENO = (
    'web-1  | 2026-11-13 18:52:45,001 1 INFO ? odoo: Odoo version 14.0\n'
    'web-1  | 2026-11-13 18:53:00,001 1 INFO %s odoo.modules.loading: loading\n'
    'web-1  | 2026-11-13 18:54:00,001 1 INFO %s odoo.addons.base.models.ir_cron: Starting job `x`.\n'
    % (BD, BD))
LOG_MALO = LOG_BUENO + 'web-1  | 2026-11-13 18:55:00,001 1 INFO otra_14 odoo.modules.loading: loading\n'


def servidor_simulado():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _resp(self, codigo, cuerpo=b'', tipo='text/html; charset=utf-8', extra=()):
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            for k, v in extra:
                self.send_header(k, v)
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _sesion(self):
            return 'session_id=ok' in (self.headers.get('Cookie') or '')

        def _carcasa(self, diseno, script=''):
            srcdoc = html.escape(PREFIJO + diseno, quote=True)
            return ('<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
                    '<iframe sandbox="allow-scripts allow-modals" srcdoc="%s"></iframe>%s'
                    '</body></html>' % (srcdoc, script)).encode()

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            q = urllib.parse.parse_qs(u.query)
            if u.path == '/web/login':
                if q.get('db') != [BD]:
                    return self._resp(400)
                return self._resp(200, (
                    '<!DOCTYPE html><form class="oe_login_form" method="post" action="/web/login">'
                    '<input name="login"><input name="password" type="password"></form>').encode())
            if not self._sesion():
                return self._resp(303, extra=[('Location', '/web/login')])
            if u.path == '/web':
                return self._resp(200, b'<!DOCTYPE html><title>web</title><p>web</p>')
            hdr = [('Content-Security-Policy', CSP_FAB), ('X-Content-Type-Options', 'nosniff')]
            if u.path == '/chatboo/canvas/1':
                return self._resp(200, self._carcasa(DISENO_LIMPIO), extra=hdr)
            if u.path == '/chatboo/canvas/2':
                return self._resp(200, self._carcasa(DISENO_SELF), extra=hdr)
            if u.path == '/chatboo/canvas/3':
                return self._resp(200, self._carcasa(
                    DISENO_LIMPIO, '<script>location.href="/web/database/selector"</script>'),
                    extra=[('X-Content-Type-Options', 'nosniff')])
            if u.path == '/chatboo/canvas/1/download':
                return self._resp(200, (PREFIJO + DISENO_LIMPIO).encode(), extra=[
                    ('Content-Disposition', 'attachment; filename="lienzo.html"'),
                    ('X-Content-Type-Options', 'nosniff')])
            if u.path.startswith('/web/database'):
                return self._resp(200, b'selector')
            return self._resp(404)

        def do_POST(self):
            u = urllib.parse.urlsplit(self.path)
            largo = int(self.headers.get('Content-Length') or 0)
            cuerpo = self.rfile.read(largo)
            if u.path == '/web/webclient/version_info':
                return self._resp(200, b'{"jsonrpc":"2.0","result":{}}', 'application/json')
            if u.path == '/web/login':
                d = urllib.parse.parse_qs(cuerpo.decode())
                if d.get('login') == ['prueba'] and d.get('password') == ['clave-prueba']:
                    return self._resp(303, extra=[('Location', '/web'),
                                                  ('Set-Cookie', 'session_id=ok; Path=/')])
                return self._resp(200, b'mal')
            if u.path == '/web/session/get_session_info' and self._sesion():
                return self._resp(200, json.dumps(
                    {'jsonrpc': '2.0', 'result': {'db': BD, 'uid': 99}}).encode(), 'application/json')
            return self._resp(404)

    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def autoprueba(args):
    fallos = 0

    def ver(nombre, cond):
        nonlocal fallos
        print('%s  %s' % ('PASA ' if cond else 'FALLA', nombre))
        fallos += 0 if cond else 1

    print('--- C sobre logs simulados')
    ver('C con solo ? y %s' % BD, comprobacion_c(io.StringIO(LOG_BUENO)))
    ver('C detecta otra BD', not comprobacion_c(io.StringIO(LOG_MALO)))
    print('--- Guardas de rutas')
    for r in ('/web/database/selector', '//evil.example/x', 'http://x/y', '/web/login?db=otra'):
        try:
            comprobar_ruta(r)
            ver('rechaza %s' % r, False)
        except SystemExit:
            ver('rechaza %s' % r, True)
    print('--- Chrome contra el servidor simulado')
    srv = servidor_simulado()
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    salida = args.salida
    ns = argparse.Namespace(salida=salida, rutas=['/chatboo/canvas/1', '/chatboo/canvas/2',
                                                  '/chatboo/canvas/3'],
                            descarga=['/chatboo/canvas/1/download'])
    capturado = io.StringIO()
    real = sys.stdout
    sys.stdout = capturado
    try:
        codigo = navegar(ns, base=base, c_func=lambda: comprobacion_c(io.StringIO(LOG_BUENO)),
                         login='prueba', clave='clave-prueba')
    finally:
        sys.stdout = real
        srv.shutdown()
    texto = capturado.getvalue()
    print(texto)
    bloques = {b.split('\n', 1)[0].strip(): b for b in texto.split('\n== ')[1:]}

    def bloque(prefijo):
        return next((v for k, v in bloques.items() if k.startswith(prefijo)), '')

    b1, b2, b3 = bloque('/chatboo/canvas/1'), bloque('/chatboo/canvas/2'), bloque('/chatboo/canvas/3')
    bd = bloque('/chatboo/canvas/1/download')
    ver('sesión de %s' % BD, ('Sesión: BD %s' % BD) in texto)
    ver('canvas/1: 2/2 pintadas, sin Refused, <meta> 2.º hijo, CSS1Compat',
        'imágenes 2/2 pintadas, 0 rotas; <meta> CSP sí (2.º hijo de <head>); CSS1Compat' in b1
        and 'Refused (consola): ninguno' in b1)
    ver('canvas/2: Refused img-src y connect-src, 1 rota',
        'img-src' in b2 and 'connect-src' in b2 and '1 rotas' in b2)
    ver('canvas/3: la guardia bloquea /web/database', 'bloqueadas: 1' in b3)
    ver('descarga desde el disco: 2/2 pintadas, sin Refused',
        'imágenes 2/2 pintadas' in bd and 'Refused (consola): ninguno' in bd)
    ver('código de salida 1 (hay incidencias simuladas)', codigo == 1)
    print('\nAutoprueba: %s' % ('todo PASA' if not fallos else '%d FALLA' % fallos))
    return 0 if not fallos else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='orden', required=True)
    sub.add_parser('c', help='C sobre un log por la entrada estándar')
    n = sub.add_parser('navegar', help='entrar y visitar rutas de lab_pns_ai_3973_14')
    n.add_argument('--salida', required=True, help='carpeta para capturas y detalle.txt')
    n.add_argument('--descarga', action='append', default=[],
                   help='ruta de una descarga, para abrirla desde el disco (repetible)')
    n.add_argument('rutas', nargs='*', help='rutas que empiezan por /, p. ej. /chatboo/canvas/8')
    a = sub.add_parser('autoprueba', help='prueba contra un servidor simulado')
    a.add_argument('--salida', required=True)
    args = ap.parse_args()
    if args.orden == 'c':
        ok = comprobacion_c(io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace'))
        return 0 if ok else 2
    if args.orden == 'navegar':
        return navegar(args)
    os.makedirs(args.salida, exist_ok=True)
    return autoprueba(args)


if __name__ == '__main__':
    sys.exit(main())
