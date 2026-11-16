#!/usr/bin/env python3
"""Laboratorio de lab_pns_ai_3973 con Chrome headless (--remote-debugging-pipe).

Solo biblioteca estándar: sin Node, sin websocket-client, sin instalar nada.

Órdenes:
  c            Comprobación C sobre un log leído por la entrada estándar
               (la misma lógica que lab_procedimiento_3973.md).
  rutas        Solo las guardas de las rutas (antes de arrancar nada).
  navegar      Entra como LAB_LOGIN/LAB_PASSWORD por /web/login?db=lab_pns_ai_3973_14,
               resume la medida del login, comprueba que la sesión es de
               lab_pns_ai_3973_14, hace C sobre el log del servidor y visita las
               rutas dadas. Por ruta: imágenes pintadas en el marco srcdoc,
               «Refused» de CSP por directiva (consola de Chrome), errores de JS
               y una captura. Bloquea cualquier petición a /web/database/*.
               Con --pintado (parche 34, L1), antes de las rutas pasa por el
               formatContent real del cliente (pns_ai_chatboo.formatters) las
               respuestas con el aviso de los casos a, a′, b, b′, c y d, en
               inglés y en español, y compara el pintado con lo previsto. No
               escribe en la BD ni llama al modelo.
  autoprueba   Lo mismo contra un servidor simulado en 127.0.0.1 (sin Odoo),
               con resultados esperados. Sirve para validar el script en el equipo.
               Con --js <carpeta static/src/js de pns_ai_chatboo>, también pasa
               el pintado por los archivos JS reales con un cargador simulado.

No imprime contenido de las páginas ni del log: solo nombres de BD, recuentos y
nombres de archivo. Los textos de los errores de JS van a <salida>/detalle.txt,
que es local y no se copia a la documentación.

Códigos de salida (los mismos que lab_auto.sh; un código por causa):
   0  todo como se espera
   1  incidencias de medición (rutas o login)
   3  otra BD (sesión, C en vivo o C de un log)
   4  el servidor no responde
   5  falla el login
   6  error de Chrome (CDP)
   7  C sin líneas de Odoo (log vacío o que no es del servidor)
   8  no concluyente: --pintado no encuentra el formateador del cliente
  11  faltan LAB_LOGIN o LAB_PASSWORD
  12  argumentos o rutas no válidos
  20  error interno de este script (traceback en la salida de errores)
 130  Ctrl+C
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
import traceback
import urllib.parse
import urllib.request

# Códigos de salida (ver el docstring). El 2 no se usa: era el «abortado» de
# antes y es también el de un error de argparse sin capturar.
OK = 0
INCIDENCIAS = 1
OTRA_BD = 3
SIN_SERVIDOR = 4
FALLA_LOGIN = 5
FALLA_CHROME = 6
C_SIN_LINEAS = 7
NO_CONCLUYENTE = 8
SIN_CREDENCIALES = 11
ARGUMENTOS = 12
INTERNO = 20
INTERRUMPIDO = 130

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
# Pintado del aviso del parche 34 (L1, sin modelo y sin escribir en la BD)
# --------------------------------------------------------------------------
# Texto del aviso: msgid de chatboo_async_request.py:1364 y su traducción en
# pns_ai_chatboo/i18n/es.po:2213-2214.
NOTAS_P34 = {
    'en': 'No page was built. The reason is in the AI History.',
    'es': 'No se ha creado la página. El motivo está en el Historial IA.',
}
# Respuestas del modelo (acc) de cada caso de «Pintado del aviso en el
# cliente» (propuesta_fase4_3973.md). El aviso lo añade componer_p34, con la
# misma regla F1 que el servidor (chatboo_async_request.py:1361-1376).
TABLA_P34 = ('<div class="o_ai_table_block table-responsive"><table class="o_ai_data_table">'
             '<tr><th>id</th><th>Nombre</th></tr><tr><td>1</td><td>A</td></tr></table></div>')
CASOS_P34 = [
    ('a', 'HTML + prosa sin marcas', TABLA_P34 + '\n\nHe actualizado el color de fondo.'),
    ('a′', 'tabla en <div> + ## / ** / lista', TABLA_P34 + '## Análisis\n\n**Total:** 1 contacto.\n\n- uno'),
    ('b', 'texto con markdown', '## Resumen\n\nHe preparado **los datos**.'),
    ('b′', 'texto llano', 'He actualizado el color de fondo.'),
    ('c', 'respuesta vacía', ''),
    ('d', 'texto + tabla incrustada', 'Aquí tienes la tabla:\n' + TABLA_P34 + '\nHe actualizado el color de fondo.'),
]
# Lo previsto: lectura de código y ejecución de los JS de la rama con un
# cargador simulado (16/11/2026). L1 lo confirma o lo desmiente en Odoo.
PREVISTO_P34 = {'a': 'cursiva', 'a′': 'etiquetas literales', 'b': 'cursiva',
                'b′': 'guiones literales', 'c': 'guiones literales', 'd': 'guiones literales'}
ESPERA_MODULO = 30  # segundos para que el cliente web exponga el formateador


def componer_p34(acc, nota):
    """El contenido guardado con aviso, como lo compone el servidor (F1)."""
    if (acc or '').lstrip().startswith('<'):
        return acc + '<p><em>' + html.escape(nota) + '</em></p>'
    if (acc or '').strip():
        return '%s\n\n_%s_' % (acc, nota)
    return '_%s_' % nota


# El formateador se busca como lo registra el cargador de Odoo 14
# (odoo.__DEBUG__.services) y, si no está, se pide con un odoo.define propio.
# Cada contenido se pasa por formatContent (lo mismo que pinta el chat,
# chatboo_component_v2.js:1226 y :5348) y se lee en un documento inerte.
PINTADO_JS = r"""(async () => {
  const casos = %(casos)s, espera = %(espera)d * 1000, fin = Date.now() + espera;
  let F = null, via = '';
  while (Date.now() < fin) {
    try {
      const s = window.odoo && odoo.__DEBUG__ && odoo.__DEBUG__.services;
      if (s && s['pns_ai_chatboo.formatters']) { F = s['pns_ai_chatboo.formatters']; via = 'services'; break; }
    } catch (e) {}
    if (window.__segesLabF) { F = window.__segesLabF; via = 'define'; break; }
    if (!window.__segesLabDef && window.odoo && typeof odoo.define === 'function') {
      window.__segesLabDef = 1;
      try {
        odoo.define('seges_lab.pintado', function (require) {
          window.__segesLabF = require('pns_ai_chatboo.formatters');
        });
      } catch (e) {}
    }
    await new Promise(r => setTimeout(r, 250));
  }
  if (!F || typeof F.formatContent !== 'function') return {via: '', res: []};
  const inerte = document.implementation.createHTMLDocument('');
  const res = [];
  for (const c of casos) {
    const h = F.formatContent(c.contenido);
    const d = inerte.createElement('div');
    d.innerHTML = h;
    const t = d.textContent;
    res.push({
      caso: c.caso, idioma: c.idioma,
      cursiva: Array.from(d.querySelectorAll('em, i')).some(e => e.textContent.indexOf(c.nota) >= 0),
      guiones: t.indexOf('_' + c.nota + '_') >= 0,
      etiquetas: /<\/?(em|p)>/.test(t),
      presente: t.indexOf(c.nota) >= 0,
      html_cliente: typeof F.isLikelyHtml === 'function' ? !!F.isLikelyHtml(c.contenido) : null,
      parte_cola: (window.ChatbooSse && ChatbooSse.splitHtmlAndMarkdownTail)
        ? !!ChatbooSse.splitHtmlAndMarkdownTail(c.contenido.trim()) : null,
      _html: h,
    });
  }
  // Muestra para la captura: los doce pintados, en una capa que se quita después.
  const capa = document.createElement('div');
  capa.id = 'seges_lab_pintado';
  capa.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#fff;overflow:auto;'
    + 'padding:8px;font-size:12px;columns:2;';
  for (const r of res) {
    const b = document.createElement('div');
    b.style.cssText = 'break-inside:avoid;border:1px solid #ccc;margin:0 0 6px;padding:4px;';
    const e = document.createElement('div');
    e.style.cssText = 'font-weight:bold;color:#555;';
    e.textContent = r.caso + ' · ' + r.idioma;
    const cuerpo = document.createElement('div');
    cuerpo.innerHTML = r._html;
    b.appendChild(e);
    b.appendChild(cuerpo);
    capa.appendChild(b);
    delete r._html;
  }
  document.body.appendChild(capa);
  return {via: via, res: res};
})()"""


def clase_pintado(r):
    if not r['presente']:
        return 'ausente'
    if r['etiquetas']:
        return 'etiquetas literales'
    if r['guiones']:
        return 'guiones literales'
    if r['cursiva']:
        return 'cursiva'
    return 'otro'


def medir_pintado(ch, salida):
    """Pintado del aviso por el formatContent real. Devuelve (incidencias, código)."""
    casos = [{'caso': k, 'idioma': idioma, 'nota': nota, 'contenido': componer_p34(acc, nota)}
             for k, _desc, acc in CASOS_P34 for idioma, nota in sorted(NOTAS_P34.items())]
    ch.nueva_medida('pintado')
    r = ch.evaluar(PINTADO_JS % {'casos': json.dumps(casos), 'espera': ESPERA_MODULO},
                   promesa=True, espera=ESPERA_MODULO + 30) or {}
    print('\n== pintado del aviso (parche 34)')
    if not r.get('res'):
        print('  formateador del cliente: NO encontrado en %d s (ni por services ni por define)'
              % ESPERA_MODULO)
        print('  Resultado del pintado: NO CONCLUYENTE')
        return [], NO_CONCLUYENTE
    print('  formateador: pns_ai_chatboo.formatters.formatContent (por %s)' % r['via'])
    iguales, incid = 0, []
    for m in r['res']:
        clase, previsto = clase_pintado(m), PREVISTO_P34[m['caso']]
        ok = clase == previsto
        iguales += ok
        if not ok:
            incid.append('pintado %s %s' % (m['caso'], m['idioma']))
        print('  %-2s %s: %-19s previsto: %-19s %s  [isLikelyHtml %s · parte la cola %s]' % (
            m['caso'], m['idioma'], clase, previsto, 'igual' if ok else 'DISTINTO',
            {True: 'sí', False: 'no', None: '?'}[m['html_cliente']],
            {True: 'sí', False: 'no', None: '?'}[m['parte_cola']]))
    print('  coincide con lo previsto: %d/%d' % (iguales, len(r['res'])))
    png = os.path.join(salida, 'pintado.png')
    ch.captura(png)
    ch.evaluar("(() => { const c = document.getElementById('seges_lab_pintado');"
               " if (c) c.remove(); return 1; })()")
    print('  captura: %s' % os.path.basename(png))
    medida = ch.medida
    errores = medida['errores_log'] + medida['errores_consola'] + medida['excepciones_js']
    print('  errores de JS durante el pintado: %d (textos en detalle.txt)' % errores)
    if errores:
        incid.append('pintado js')
    return incid, OK


# --------------------------------------------------------------------------
# Comprobación C (idéntica a la del procedimiento)
# --------------------------------------------------------------------------
PAT_C = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ \S+ (\S+) (\S+): (.*)")


def resultado_c(lineas_log):
    """C con código: OK, OTRA_BD o C_SIN_LINEAS (ninguna línea de Odoo)."""
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
    if not lineas:
        # Un log sin ninguna línea de Odoo no prueba nada: no es «OK».
        print("C: SIN LÍNEAS DE ODOO (log vacío o que no es del servidor)")
        return C_SIN_LINEAS
    if set(lineas) <= PERMITIDAS and set(crons) <= {BD}:
        print("C: OK")
        return OK
    print("C: OTRA BD (parar: «Si aparece otra BD»)")
    return OTRA_BD


def comprobacion_c(lineas_log):
    return resultado_c(lineas_log) == OK


def c_en_vivo():
    """C sobre `odoo-dev 14 log all`, ejecutado desde la carpeta del laboratorio."""
    salida = subprocess.run(
        ['odoo-dev', '14', 'log', 'all'], cwd=LAB,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    ).stdout
    return resultado_c(io.StringIO(salida.decode('utf-8', 'replace')))


# --------------------------------------------------------------------------
# Chrome por tubería
# --------------------------------------------------------------------------
class ErrorCDP(Exception):
    pass


class ErrorLogin(Exception):
    """El login no se completó (formulario, envío o sesión)."""


class ErrorRuta(Exception):
    """Una ruta no pasa las guardas."""


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

    def evaluar(self, expr, sesion=None, contexto=None, promesa=False, espera=30):
        p = {'expression': expr, 'returnByValue': True, 'awaitPromise': promesa}
        if contexto:
            p['contextId'] = contexto
        r = self.llamar('Runtime.evaluate', p, sesion or self.pagina, espera=espera)
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
        raise ErrorRuta('ruta no válida (debe empezar por una sola /): %s' % ruta)
    if '/web/database' in ruta:
        raise ErrorRuta('ruta prohibida: %s' % ruta)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(ruta).query)
    if any(v != BD for v in q.get('db', [])):
        raise ErrorRuta('ruta con otra BD: %s' % ruta)


def comprobar_rutas(rutas):
    """Guardas de todas las rutas; código OK o ARGUMENTOS."""
    try:
        for r in rutas:
            comprobar_ruta(r)
    except ErrorRuta as e:
        print('ABORTADO: %s' % e)
        return ARGUMENTOS
    return OK


def nombre_archivo(ruta):
    return re.sub(r'[^A-Za-z0-9]+', '_', ruta).strip('_') or 'raiz'


def resumir(ruta, error, marcos, medida, captura, con_marcos=True):
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
    if con_marcos and not marcos:
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
        raise ErrorLogin('login: ' + err)
    js = (
        "(() => { const f = document.querySelector('form.oe_login_form');"
        " if (!f) return 'sin-formulario';"
        " f.querySelector('input[name=login]').value = %s;"
        " f.querySelector('input[name=password]').value = %s;"
        " f.submit(); return 'ok'; })()" % (json.dumps(login), json.dumps(clave)))
    ch.cargas = 0
    if ch.evaluar(js) != 'ok':
        raise ErrorLogin('login: no está el formulario de /web/login')
    if not ch.esperar(lambda: ch.cargas >= 1, 90):
        raise ErrorLogin('login: la página tras el envío no cargó')
    ruta = ch.evaluar('location.pathname')
    if not ruta.startswith('/web') or ruta.startswith('/web/login'):
        raise ErrorLogin('login: no entró (ruta %s)' % ruta)
    info = ch.evaluar(
        "fetch('/web/session/get_session_info', {method: 'POST',"
        " headers: {'Content-Type': 'application/json'},"
        " body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {}})})"
        ".then(r => r.json()).then(j => ({db: j.result && j.result.db,"
        " uid: j.result && j.result.uid}))", promesa=True)
    return info


def navegar(args, base=BASE, c_func=c_en_vivo, login=None, clave=None, espera_servidor=120):
    login = login or os.environ.get('LAB_LOGIN')
    clave = clave or os.environ.get('LAB_PASSWORD')
    if not login or not clave:
        print('ABORTADO: faltan LAB_LOGIN y LAB_PASSWORD en el entorno.')
        return SIN_CREDENCIALES
    codigo = comprobar_rutas(args.rutas + args.descarga)
    if codigo:
        return codigo
    os.makedirs(args.salida, exist_ok=True)
    print('Esperando al servidor…')
    if not esperar_servidor(base, espera_servidor):
        print('ABORTADO: el servidor no responde en %s' % base)
        return SIN_SERVIDOR
    perfil = tempfile.mkdtemp(prefix='lab3973-chrome-')
    descargas = tempfile.mkdtemp(prefix='lab3973-descargas-')
    try:
        ch = Chrome(perfil, args.salida)
    except OSError as e:
        print('ABORTADO: Chrome no arranca (%s)' % e.__class__.__name__)
        shutil.rmtree(perfil, ignore_errors=True)
        shutil.rmtree(descargas, ignore_errors=True)
        return FALLA_CHROME
    incidencias = []
    no_concluyente = False
    try:
        ch.abrir_pagina(descargas)
        ch.nueva_medida('login')
        info = entrar(ch, base, login, clave)
        # Lo que el cliente web emite justo después de entrar es del login,
        # no de la primera ruta.
        ch.bombear(ESPERA_PINTADO)
        print('Sesión: BD %s, uid %s' % (info.get('db'), info.get('uid')))
        incidencias += [('login', i) for i in resumir(
            'login', None, [], ch.medida, None, con_marcos=False)]
        if info.get('db') != BD:
            print('ABORTADO: la sesión no es de %s' % BD)
            return OTRA_BD
        print('\nComprobación C tras la entrada:')
        codigo = c_func()
        if codigo:
            print('ABORTADO: C tras la entrada (código %d)' % codigo)
            return codigo
        if getattr(args, 'pintado', False):
            incid, codigo = medir_pintado(ch, args.salida)
            incidencias += [('pintado', i) for i in incid]
            no_concluyente = codigo == NO_CONCLUYENTE
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
    except ErrorLogin as e:
        print('ABORTADO: %s' % e)
        return FALLA_LOGIN
    except ErrorCDP as e:
        print('ABORTADO: %s' % e)
        return FALLA_CHROME
    finally:
        ch.cerrar()
        shutil.rmtree(perfil, ignore_errors=True)
        shutil.rmtree(descargas, ignore_errors=True)
    print('\nResultado: %s' % ('sin incidencias' if not incidencias else
                               'incidencias: ' + '; '.join('%s → %s' % x for x in incidencias)))
    if no_concluyente:
        print('Pintado del aviso: NO CONCLUYENTE (formateador del cliente no encontrado)')
    print('Peticiones a /web/database bloqueadas en total: %d' % ch.bloqueadas)
    if incidencias:
        return INCIDENCIAS
    return NO_CONCLUYENTE if no_concluyente else OK


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


# Cliente simulado para --pintado. FORMATEADOR_SIMULADO reproduce lo previsto
# (no es el JS del fabricante: con --js se usan los archivos reales).
FORMATEADOR_SIMULADO = r'''
function segesEsc(t) { return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function segesFormatea(s) {
  if (s.charAt(0) === '<') {
    if (s.indexOf('## ') >= 0) { var i = s.indexOf('</div>') + 6; return s.slice(0, i) + '<p>' + segesEsc(s.slice(i)) + '</p>'; }
    return s;
  }
  if (s.indexOf('## ') >= 0) { return segesEsc(s).replace(/_([^_]+)_/g, '<em>$1</em>'); }
  return segesEsc(s);
}
'''
CLIENTES_SIMULADOS = {
    # Como Odoo 14: el módulo aparece en odoo.__DEBUG__.services al cabo de un rato.
    'services': FORMATEADOR_SIMULADO + '''
window.odoo = {__DEBUG__: {services: {}}};
setTimeout(function () { odoo.__DEBUG__.services['pns_ai_chatboo.formatters'] =
  {formatContent: segesFormatea, isLikelyHtml: function (c) { return c.trim().charAt(0) === '<'; }}; }, 600);
''',
    # Sin services: solo se llega al módulo con un odoo.define propio.
    'define': FORMATEADOR_SIMULADO + '''
window.odoo = {define: function (nombre, fabrica) {
  fabrica(function (m) { return m === 'pns_ai_chatboo.formatters' ? {formatContent: segesFormatea} : null; }); }};
''',
    # El cliente no expone el formateador: NO CONCLUYENTE.
    'sin_modulo': 'window.odoo = {define: function () {}};',
    # Un cliente que escapa siempre: pintado distinto de lo previsto.
    'distinto': FORMATEADOR_SIMULADO + '''
window.odoo = {__DEBUG__: {services: {'pns_ai_chatboo.formatters': {formatContent: segesEsc}}}};
''',
}
# Cargador mínimo para los JS reales: como odoo.define de Odoo 14 con
# require('web.core') y registro en odoo.__DEBUG__.services.
CARGADOR_REAL = '''
window.odoo = {__DEBUG__: {services: {}}, define: function (nombre, fabrica) {
  var req = function (m) { return m === 'web.core' ? {_t: function (t) { return t; }} : odoo.__DEBUG__.services[m]; };
  odoo.__DEBUG__.services[nombre] = fabrica(req); }};
'''
JS_REALES = ('chatboo_sse.js', 'chatboo_markdown.js', 'chatboo_formatters.js')


def servidor_simulado(error_js_login=False, bd_sesion=BD, cliente=None, js_dir=None):
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
                extra_js = (b'<script>console.error("seges-login-js")</script>'
                            if error_js_login else b'')
                if js_dir:
                    extra_js += ('<script>%s</script>' % CARGADOR_REAL).encode()
                    extra_js += ''.join('<script src="/seges_js/%s"></script>' % n
                                        for n in JS_REALES).encode()
                elif cliente:
                    extra_js += ('<script>%s</script>' % CLIENTES_SIMULADOS[cliente]).encode()
                return self._resp(200, b'<!DOCTYPE html><title>web</title><p>web</p>' + extra_js)
            if js_dir and u.path.startswith('/seges_js/') and u.path[10:] in JS_REALES:
                with open(os.path.join(js_dir, u.path[10:]), 'rb') as f:
                    return self._resp(200, f.read(), 'text/javascript; charset=utf-8')
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
                    {'jsonrpc': '2.0', 'result': {'db': bd_sesion, 'uid': 99}}).encode(),
                    'application/json')
            return self._resp(404)

    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _navegar_capturado(ns, base, **kw):
    """navegar() con la salida estándar capturada; devuelve (código, texto)."""
    capturado = io.StringIO()
    real = sys.stdout
    sys.stdout = capturado
    try:
        codigo = navegar(ns, base=base, **kw)
    finally:
        sys.stdout = real
    return codigo, capturado.getvalue()


def _bloques(texto):
    return {b.split('\n', 1)[0].strip(): b for b in texto.split('\n== ')[1:]}


def _bloque(bloques, prefijo):
    return next((v for k, v in bloques.items() if k.startswith(prefijo)), '')


def autoprueba(args):
    global CHROME
    fallos = 0

    def ver(nombre, cond):
        nonlocal fallos
        print('%s  %s' % ('PASA ' if cond else 'FALLA', nombre))
        fallos += 0 if cond else 1

    def c_bueno():
        return resultado_c(io.StringIO(LOG_BUENO))

    def sub_carpeta(nombre):
        ruta = os.path.join(args.salida, nombre)
        os.makedirs(ruta, exist_ok=True)
        return ruta

    nulo = io.StringIO()
    print('--- C sobre logs simulados')
    ver('C con solo ? y %s' % BD, comprobacion_c(io.StringIO(LOG_BUENO)))
    ver('C detecta otra BD', not comprobacion_c(io.StringIO(LOG_MALO)))
    real = sys.stdout
    sys.stdout = nulo
    try:
        codigos_c = (resultado_c(io.StringIO(LOG_BUENO)), resultado_c(io.StringIO(LOG_MALO)),
                     resultado_c(io.StringIO('')), resultado_c(io.StringIO('sin formato\n')))
    finally:
        sys.stdout = real
    ver('códigos de C: 0 OK, 3 otra BD, 7 log vacío, 7 log sin líneas de Odoo',
        codigos_c == (OK, OTRA_BD, C_SIN_LINEAS, C_SIN_LINEAS))
    print('--- Guardas de rutas')
    for r in ('/web/database/selector', '//evil.example/x', 'http://x/y', '/web/login?db=otra'):
        try:
            comprobar_ruta(r)
            ver('rechaza %s' % r, False)
        except ErrorRuta:
            ver('rechaza %s' % r, True)
    print('--- Códigos de la línea de órdenes (sin Chrome)')
    yo = os.path.abspath(__file__)

    def orden(*a, entorno=None):
        e = dict(os.environ)
        e.pop('LAB_LOGIN', None)
        e.pop('LAB_PASSWORD', None)
        e.update(entorno or {})
        return subprocess.run([sys.executable, '-I', yo] + list(a), env=e,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              stdin=subprocess.DEVNULL).returncode
    ver('rutas válidas → 0', orden('rutas', '--descarga', '/chatboo/canvas/1/download',
                                   '/chatboo/canvas/1') == OK)
    ver('rutas con /web/database → 12', orden('rutas', '/web/database/selector') == ARGUMENTOS)
    ver('argumentos mal formados → 12', orden('navegar') == ARGUMENTOS)
    ver('orden desconocida → 12', orden('no-existe') == ARGUMENTOS)
    ver('navegar sin credenciales → 11',
        orden('navegar', '--salida', sub_carpeta('sin_credenciales'), '/chatboo/canvas/1')
        == SIN_CREDENCIALES)
    sys.stderr, err_real = io.StringIO(), sys.stderr
    try:
        ver('excepción interna → 20 (traceback a la salida de errores)',
            ejecutar(lambda: 1 // 0) == INTERNO)
    finally:
        sys.stderr = err_real

    print('--- Chrome contra el servidor simulado')
    srv = servidor_simulado()
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    ns = argparse.Namespace(salida=sub_carpeta('principal'),
                            rutas=['/chatboo/canvas/1', '/chatboo/canvas/2', '/chatboo/canvas/3'],
                            descarga=['/chatboo/canvas/1/download'])
    try:
        codigo, texto = _navegar_capturado(ns, base, c_func=c_bueno,
                                           login='prueba', clave='clave-prueba')
    finally:
        srv.shutdown()
    print(texto)
    bloques = _bloques(texto)
    b1, b2, b3 = (_bloque(bloques, '/chatboo/canvas/1'), _bloque(bloques, '/chatboo/canvas/2'),
                  _bloque(bloques, '/chatboo/canvas/3'))
    bd = _bloque(bloques, '/chatboo/canvas/1/download')
    bl = _bloque(bloques, 'login')
    ver('sesión de %s' % BD, ('Sesión: BD %s' % BD) in texto)
    ver('login resumido: sin Refused, 0 errores de JS, sin marco exigido',
        'Refused (consola): ninguno' in bl and 'errores de JS: 0' in bl
        and 'ninguno medido' not in bl and 'login →' not in texto)
    ver('canvas/1: 2/2 pintadas, sin Refused, <meta> 2.º hijo, CSS1Compat',
        'imágenes 2/2 pintadas, 0 rotas; <meta> CSP sí (2.º hijo de <head>); CSS1Compat' in b1
        and 'Refused (consola): ninguno' in b1)
    ver('canvas/2: Refused img-src y connect-src, 1 rota',
        'img-src' in b2 and 'connect-src' in b2 and '1 rotas' in b2)
    ver('canvas/3: la guardia bloquea /web/database', 'bloqueadas: 1' in b3)
    ver('descarga desde el disco: 2/2 pintadas, sin Refused',
        'imágenes 2/2 pintadas' in bd and 'Refused (consola): ninguno' in bd)
    ver('código de salida 1 (hay incidencias simuladas)', codigo == INCIDENCIAS)

    print('--- Variantes (una ejecución corta cada una)')
    corto = dict(rutas=['/chatboo/canvas/1'], descarga=[])
    srv = servidor_simulado(error_js_login=True)
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    try:
        codigo, texto = _navegar_capturado(
            argparse.Namespace(salida=sub_carpeta('login_js'), **corto), base,
            c_func=c_bueno, login='prueba', clave='clave-prueba')
    finally:
        srv.shutdown()
    bl = _bloque(_bloques(texto), 'login')
    ver('error de JS en el login → incidencia «login → js», código 1',
        codigo == INCIDENCIAS and 'errores de JS: 1' in bl and 'login → js' in texto
        and '/chatboo/canvas/1 →' not in texto)

    srv = servidor_simulado(bd_sesion='otra_14')
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    try:
        codigo, texto = _navegar_capturado(
            argparse.Namespace(salida=sub_carpeta('otra_bd'), **corto), base,
            c_func=c_bueno, login='prueba', clave='clave-prueba')
        ver('sesión de otra BD → 3', codigo == OTRA_BD and 'la sesión no es de' in texto)
        codigo, texto = _navegar_capturado(
            argparse.Namespace(salida=sub_carpeta('login_malo'), **corto), base,
            c_func=c_bueno, login='prueba', clave='otra-clave')
        ver('contraseña mala → 5', codigo == FALLA_LOGIN)
    finally:
        srv.shutdown()

    srv = servidor_simulado()
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    try:
        for nombre, c_func, esperado in (
                ('C en vivo con otra BD → 3', lambda: OTRA_BD, OTRA_BD),
                ('C en vivo sin líneas de Odoo → 7', lambda: C_SIN_LINEAS, C_SIN_LINEAS)):
            codigo, texto = _navegar_capturado(
                argparse.Namespace(salida=sub_carpeta('c_%d' % esperado), **corto), base,
                c_func=c_func, login='prueba', clave='clave-prueba')
            ver(nombre, codigo == esperado and '== /chatboo/canvas/1' not in texto)
        chrome_real = CHROME
        CHROME = os.path.join(args.salida, 'no-existe-chrome')
        try:
            codigo, texto = _navegar_capturado(
                argparse.Namespace(salida=sub_carpeta('sin_chrome'), **corto), base,
                c_func=c_bueno, login='prueba', clave='clave-prueba')
        finally:
            CHROME = chrome_real
        ver('Chrome que no arranca → 6', codigo == FALLA_CHROME)
    finally:
        srv.shutdown()

    srv = servidor_simulado()
    puerto = srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    codigo, texto = _navegar_capturado(
        argparse.Namespace(salida=sub_carpeta('sin_servidor'), **corto),
        'http://127.0.0.1:%d' % puerto, c_func=c_bueno, login='prueba',
        clave='clave-prueba', espera_servidor=3)
    ver('servidor que no responde → 4', codigo == SIN_SERVIDOR)

    print('--- Pintado del aviso (--pintado, parche 34)')
    global ESPERA_MODULO
    ver('rutas --pintado → 0', orden('rutas', '--pintado') == OK)
    ver('seis casos, cada uno con su previsto',
        len(CASOS_P34) == 6 and set(PREVISTO_P34) == {k for k, _d, _a in CASOS_P34})
    ver('composición F1 como el servidor',
        componer_p34('<p>x</p>', 'N.') == '<p>x</p><p><em>N.</em></p>'
        and componer_p34('x', 'N.') == 'x\n\n_N._' and componer_p34('', 'N.') == '_N._'
        and componer_p34('  ', 'N.') == '_N._')
    solo_pintado = dict(rutas=[], descarga=[], pintado=True)
    espera_real = ESPERA_MODULO
    ESPERA_MODULO = 3
    try:
        for cliente, nombre, esperado, textos in (
                ('services', 'cliente como Odoo 14 (services) → 12/12, código 0', OK,
                 ('(por services)', 'coincide con lo previsto: 12/12', 'captura: pintado.png')),
                ('define', 'cliente sin services (odoo.define propio) → 12/12, código 0', OK,
                 ('(por define)', 'coincide con lo previsto: 12/12')),
                ('distinto', 'pintado distinto de lo previsto → código 1', INCIDENCIAS,
                 ('DISTINTO', 'pintado → pintado a en')),
                ('sin_modulo', 'formateador no encontrado → 8 (no concluyente)', NO_CONCLUYENTE,
                 ('NO encontrado', 'NO CONCLUYENTE'))):
            srv = servidor_simulado(cliente=cliente)
            base = 'http://127.0.0.1:%d' % srv.server_address[1]
            carpeta = sub_carpeta('pintado_' + cliente)
            try:
                codigo, texto = _navegar_capturado(
                    argparse.Namespace(salida=carpeta, **solo_pintado), base,
                    c_func=c_bueno, login='prueba', clave='clave-prueba')
            finally:
                srv.shutdown()
            if cliente == 'services':
                print(_bloque(_bloques(texto), 'pintado'))
            ver(nombre, codigo == esperado and all(t in texto for t in textos)
                and (cliente == 'sin_modulo') == ('pintado.png' not in os.listdir(carpeta)))
        if args.js:
            srv = servidor_simulado(js_dir=os.path.abspath(args.js))
            base = 'http://127.0.0.1:%d' % srv.server_address[1]
            try:
                codigo, texto = _navegar_capturado(
                    argparse.Namespace(salida=sub_carpeta('pintado_js_reales'), **solo_pintado),
                    base, c_func=c_bueno, login='prueba', clave='clave-prueba')
            finally:
                srv.shutdown()
            print(_bloque(_bloques(texto), 'pintado'))
            ver('JS reales de %s con cargador simulado → 12/12, código 0' % args.js,
                codigo == OK and 'coincide con lo previsto: 12/12' in texto)
    finally:
        ESPERA_MODULO = espera_real

    print('\nAutoprueba: %s' % ('todo PASA' if not fallos else '%d FALLA' % fallos))
    return OK if not fallos else INCIDENCIAS


class _Argumentos(argparse.ArgumentParser):
    """argparse sale con 2 por defecto; aquí, con ARGUMENTOS (12)."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(ARGUMENTOS, '%s: error: %s\n' % (self.prog, message))


def _main():
    ap = _Argumentos(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='orden', required=True, parser_class=_Argumentos)
    sub.add_parser('c', help='C sobre un log por la entrada estándar')
    r = sub.add_parser('rutas', help='solo las guardas de las rutas')
    r.add_argument('--descarga', action='append', default=[])
    r.add_argument('--pintado', action='store_true')
    r.add_argument('rutas', nargs='*')
    n = sub.add_parser('navegar', help='entrar y visitar rutas de lab_pns_ai_3973_14')
    n.add_argument('--salida', required=True, help='carpeta para capturas y detalle.txt')
    n.add_argument('--descarga', action='append', default=[],
                   help='ruta de una descarga, para abrirla desde el disco (repetible)')
    n.add_argument('--pintado', action='store_true',
                   help='pintado del aviso del parche 34 por el formatContent real (L1)')
    n.add_argument('rutas', nargs='*', help='rutas que empiezan por /, p. ej. /chatboo/canvas/8')
    a = sub.add_parser('autoprueba', help='prueba contra un servidor simulado')
    a.add_argument('--salida', required=True)
    a.add_argument('--js', help='carpeta static/src/js de pns_ai_chatboo (pintado con los JS reales)')
    args = ap.parse_args()
    if args.orden == 'c':
        return resultado_c(io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace'))
    if args.orden == 'rutas':
        return comprobar_rutas(args.rutas + args.descarga)
    if args.orden == 'navegar':
        return navegar(args)
    os.makedirs(args.salida, exist_ok=True)
    return autoprueba(args)


def ejecutar(funcion):
    """Ejecuta la orden y traduce lo inesperado a un código propio."""
    try:
        return funcion()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print('\nInterrumpido (Ctrl+C).')
        return INTERRUMPIDO
    except Exception:
        traceback.print_exc()
        print('ERROR INTERNO de lab_cdp.py (traceback en la salida de errores).')
        return INTERNO


if __name__ == '__main__':
    sys.exit(ejecutar(_main))
