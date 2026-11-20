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
               inglés y en español, y compara el pintado con lo previsto
               (desde D25, línea llana: sin marcas a la vista). No
               escribe en la BD ni llama al modelo.
               Con --escenario p34 (parche 34, L2), después del pintado y antes
               de las rutas hace los turnos reales T1, T1b, V2, 5b′, 6c y 6d′
               en Chatboo, con dos pausas para que Sergio quite y vuelva a
               marcar «Design» en una segunda ventana (cookies aparte), y
               comprueba cada paso con SQL de solo lectura. Con --visible,
               Chrome se ve (perfil temporal igualmente).
               Con --escenario tarjeta (D47, 17/11/2026), tras la C: comprueba
               por SQL que la operación plantada por tarjeta_plantar.sh sigue
               pendiente y sin caducar, abre el panel de Chatboo (pinta la
               tarjeta), quita «disabled» al botón Confirmar y lo pulsa antes
               de los 5 s (camino FORZADO: una persona no puede, el botón está
               deshabilitado durante la cuenta atrás) y mide por CDP (Network)
               el rechazo too_soon, que no hay /verification/pending sin peek
               tras el clic, la confirmación sola unos 5,5 s después con el
               mismo token, el /execute y, por SQL, la operación ejecutada.
               En el log del servidor cuenta las líneas del anexo de PNS-26.
  sqlprueba    Las consultas del escenario p34 (o, con --escenario tarjeta,
               las del escenario tarjeta) contra la BD real, en solo lectura
               (con db en marcha), para validarlas antes del laboratorio.

--lab <carpeta> y --bd <bd> (D44, 17/11/2026) en c, rutas, navegar y
sqlprueba: carpeta de ~/GitHub desde la que se lee el log y BD esperada (login,
sesión, C, guardas de rutas y SQL). Por defecto, lab_pns_ai_3973 y
lab_pns_ai_3973_14.
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
   8  no concluyente: --pintado no encuentra el formateador del cliente, o
      un paso del escenario p34 no prueba nada (error del proveedor, turno
      sin fin o un desenlace del modelo que no pasa por el parche), o en el
      escenario tarjeta el chat no se abre o la tarjeta no se pinta
   9  escenario p34: una condición o un paso manual no confirmado por SQL;
      escenario tarjeta: la operación plantada no está lista (no pendiente,
      caducada, de otro usuario…) o el SQL no se pudo hacer
  11  faltan LAB_LOGIN o LAB_PASSWORD
  12  argumentos o rutas no válidos
  20  error interno de este script (traceback en la salida de errores)
 130  Ctrl+C
"""
import argparse
import base64
import collections
import fcntl
import hashlib
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
NO_CONFIRMADO = 9
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
# misma regla que el servidor: desde D25 (16/11/2026), una línea llana, sin
# marcas (chatboo_async_request.py, bloque del parche 34 de _save_to_session).
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
# Lo previsto con la línea llana (D25): el aviso se lee sin marcas a la vista
# en los seis casos (ejecución de los JS de la rama con un cargador simulado,
# 16/11/2026). Con F1, L1 dio: a y b, cursiva; a′, etiquetas literales; b′, c
# y d, guiones literales (registro de laboratorios, 16/11/2026).
PREVISTO_P34 = {k: 'línea llana' for k in ('a', 'a′', 'b', 'b′', 'c', 'd')}
ESPERA_MODULO = 30  # segundos para que el cliente web exponga el formateador


def componer_p34(acc, nota):
    """El contenido guardado con aviso, como lo compone el servidor (D25)."""
    if (acc or '').strip():
        return '%s\n\n%s' % (acc, nota)
    return nota


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
    return 'línea llana'


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

    def __init__(self, perfil, salida, visible=False):
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
        if visible:
            args.remove('--headless=new')
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
        self.alertas = 0
        self.otros_dialogos = 0
        self.admin = None          # destino de la segunda ventana (escenario p34)
        self.admin_ctx = None
        self.admin_sesiones = set()
        # Escenario tarjeta (D47): peticiones de la página a /pns_ai_mcp/verification/*
        # (fetch y XHR), en orden. None: no se registra nada.
        self.red = None
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
        de_admin = s in self.admin_sesiones
        if metodo == 'Target.attachedToTarget':
            if p.get('targetInfo', {}).get('type') in ('iframe', 'page'):
                if de_admin:
                    self.admin_sesiones.add(p['sessionId'])
                else:
                    self.sesiones.append(p['sessionId'])
                self._preparar(p['sessionId'], esperar_respuesta=False)
        elif metodo == 'Target.detachedFromTarget':
            if p.get('sessionId') in self.sesiones:
                self.sesiones.remove(p['sessionId'])
            self.admin_sesiones.discard(p.get('sessionId'))
        elif metodo == 'Page.javascriptDialogOpening':
            # Un alert() sin cerrar detiene la página: se cuenta y se acepta.
            if p.get('type') == 'alert' and not de_admin:
                self.alertas += 1
            else:
                self.otros_dialogos += 1
            self._enviar('Page.handleJavaScriptDialog', {'accept': True}, s)
        elif de_admin and metodo != 'Fetch.requestPaused':
            # Lo que haga Sergio en la segunda ventana no es una medida.
            return
        elif metodo == 'Fetch.requestPaused':
            self.bloqueadas += 1
            self._anotar('bloqueadas_por_guardia')
            self._enviar('Fetch.failRequest',
                         {'requestId': p['requestId'], 'errorReason': 'BlockedByClient'}, s)
        elif metodo == 'Network.requestWillBeSent' and self.red is not None and s == self.pagina:
            req = p.get('request') or {}
            reg = peticion_verificacion(req.get('url', ''), req.get('postData'), p.get('timestamp'))
            if reg is not None:
                reg['id'] = p.get('requestId')
                self.red.append(reg)
        elif metodo == 'Network.responseReceived' and self.red is not None and s == self.pagina:
            for reg in self.red:
                if reg.get('id') == p.get('requestId') and reg['t_resp'] is None:
                    reg['t_resp'] = p.get('timestamp')
                    reg['http'] = (p.get('response') or {}).get('status')
        elif metodo == 'Network.loadingFinished' and self.red is not None and s == self.pagina:
            for reg in self.red:
                if reg.get('id') == p.get('requestId'):
                    reg['terminada'] = True
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

    def abrir_admin(self, url):
        """Segunda ventana con cookies aparte y la misma guardia de /web/database."""
        self.admin_ctx = self.llamar('Target.createBrowserContext')['browserContextId']
        self.admin = self.llamar('Target.createTarget', {
            'url': 'about:blank', 'browserContextId': self.admin_ctx, 'newWindow': True})['targetId']
        s = self.llamar('Target.attachToTarget', {'targetId': self.admin, 'flatten': True})['sessionId']
        self.admin_sesiones.add(s)
        self._preparar(s, esperar_respuesta=True)
        self.llamar('Page.navigate', {'url': url}, s)

    def cerrar_admin(self):
        for metodo, params in (('Target.closeTarget', {'targetId': self.admin}),
                               ('Target.disposeBrowserContext', {'browserContextId': self.admin_ctx})):
            try:
                if self.admin:
                    self.llamar(metodo, params, espera=10)
            except ErrorCDP:
                pass
        self.admin = self.admin_ctx = None

    def esperar_linea(self, pregunta):
        """Una línea de la terminal, atendiendo a Chrome mientras se espera.

        Devuelve None si la entrada estándar se cierra.
        """
        sys.stdout.write(pregunta)
        sys.stdout.flush()
        while True:
            listos, _, _ = select.select([sys.stdin, self.rd], [], [], 1)
            if self.rd in listos:
                self._leer(0)
            if sys.stdin in listos:
                linea = sys.stdin.readline()
                return linea if linea else None

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


# --------------------------------------------------------------------------
# Escenario p34 (parche 34, L2): turnos reales con el proveedor
# --------------------------------------------------------------------------
# Diseño: decisiones D20 a D24 de Sergio (16/11/2026) y las del 16/11 por la
# tarde (segunda ventana para «Design», 600 s por turno, dos intentos en 6d′).
# Nunca se imprimen contenidos: solo booleanos, recuentos e ids.
PROVEEDOR_P34 = 2
NOMBRE_PLANTADA = 'Seges P34 lienzo plantado (D24)'
ESPERA_TURNO = 600  # segundos por turno (--espera-turno)
ASIENTO = 3  # segundos sin «pensando» para dar un turno o una carga por acabados
SONDEO = 1  # segundos entre dos lecturas del estado del chat
INTENTOS_PAUSA = 3
INTENTOS_6D = 2
FALLOS_PARA_PREGUNTAR = 2  # pasos seguidos con el proveedor caído antes de preguntar si se sigue
MOTIVO_SIN_DESIGN = 'no design provider'
MOTIVO_MARCADO = 'the change left a value of the page as markup'
# En inglés desde el 17/11/2026 (opción A de Sergio): seges_int está en en_US y
# el servidor elige las frases que activan el paquete page_tab por el idioma
# del usuario (pns_ai_mcp/models/ai_context.py:79-80); «página» no coincide con
# «page» (discovery_page_tab.json) y sin page_tab el modelo no conoce page_url.
MENSAJES_P34 = {
    'T1': ('Make me a page with the first five contacts sorted by name, with only their id and '
           'name. A new page; do not write the table in the chat.'),
    'T1b': 'Make me a page with those five contacts and also write the table here, in the chat.',
    'V2': 'Now create the page with those five contacts, with their id and name.',
    '5b′': 'Make a page with the contacts whose name starts with "Seges P34", with their name and id',
    '6c': 'redo the table as cards',
    '6d′': ('Change only the background colour of this page to blue, without querying data again '
            'or changing anything else'),
}
# Motivos fijos de log_no_page (chatboo_session.py:909-1241, chatboo_canvas.py:731-1043);
# de una excepción solo se toma el nombre de la clase.
MOTIVOS_FIJOS = (
    ('the change left a value of the page as markup', 'valor en crudo'),
    ('no design provider', 'sin proveedor Design'),
    ('the design model returned nothing', 'Design no devolvió nada'),
    ('the open page has no figures to keep', 'página sin cifras que conservar'),
    ('no page is open to change', 'ninguna página abierta'),
    ('could not store the page', 'no se pudo guardar'),
    ('page_html', 'page_html'),
)
# Solo lectura: la transacción no puede escribir aunque la consulta lo intentara.
PSQL = ['docker', 'exec', '-i', '-e', 'PGOPTIONS=-c default_transaction_read_only=on',
        'odoo-dev-14-db-1', 'psql', '-X', '-q', '-U', 'odoo', '-d', BD,
        '-v', 'ON_ERROR_STOP=1', '-At', '-F', '|']

# --lab y --bd (D44, 17/11/2026). Sin ellas, lo de siempre.
LAB_POR_DEFECTO = 'lab_pns_ai_3973'
BD_POR_DEFECTO = 'lab_pns_ai_3973_14'
RE_NOMBRE_LAB = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$')
RE_NOMBRE_BD = re.compile(r'^[a-z0-9_]+$')


def configurar(lab=None, bd=None):
    """Carpeta del laboratorio (en ~/GitHub) y BD esperada. Devuelve un error o None.

    Cambia BD, LAB, PERMITIDAS y la BD de PSQL: lo usan la C, el login, la
    comprobación de la sesión, las guardas de las rutas y el SQL.
    """
    global BD, LAB, PERMITIDAS, PSQL
    lab = LAB_POR_DEFECTO if lab is None else lab
    bd = BD_POR_DEFECTO if bd is None else bd
    if not RE_NOMBRE_LAB.match(lab) or '..' in lab:
        return '--lab no válido (solo el nombre de una carpeta de ~/GitHub): %r' % lab
    if not RE_NOMBRE_BD.match(bd):
        return '--bd no válida (minúsculas, cifras y _): %r' % bd
    BD = bd
    LAB = os.path.join(os.path.expanduser('~/GitHub'), lab)
    PERMITIDAS = {'?', BD}
    PSQL = PSQL[:PSQL.index('-d') + 1] + [BD] + PSQL[PSQL.index('-d') + 2:]
    return None
RE_MARCA_TIEMPO = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$')
RE_COLUMNA = re.compile(r'^[a-z_][a-z0-9_]*$')
HOSTIL_SQL = "'</script><script>alert'"
ESCAPADO_SQL = ("chr(92) || 'u003c/script' || chr(92) || 'u003e' || chr(92) || 'u003cscript' "
                "|| chr(92) || 'u003ealert'")
ESCAPADO_TABLA_SQL = "'&lt;/script&gt;&lt;script&gt;alert'"


class ErrorSQL(Exception):
    """Una consulta de solo lectura no se pudo hacer o no devolvió lo esperado."""


def sql(consulta):
    """Filas de una consulta de solo lectura (lista de listas de texto)."""
    try:
        r = subprocess.run(PSQL, input=consulta.encode('utf-8'), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ErrorSQL('psql no se pudo ejecutar (%s)' % e.__class__.__name__)
    if r.returncode:
        # El error de psql nombra tablas y columnas, no datos.
        primera = (r.stderr.decode('utf-8', 'replace').strip().splitlines() or [''])[0]
        raise ErrorSQL('psql terminó con %d: %s' % (r.returncode, primera[:200]))
    return [linea.split('|') for linea in r.stdout.decode('utf-8', 'replace').splitlines() if linea]


def _t(valor):
    return valor == 't'


class Consultas:
    """Las consultas del escenario. Todas de solo lectura y sin contenidos."""

    def __init__(self, ejecutar=sql):
        self.ejecutar = ejecutar
        self._rel = None

    def una(self, consulta, campos):
        filas = self.ejecutar(consulta)
        if len(filas) != 1 or len(filas[0]) != campos:
            raise ErrorSQL('se esperaba 1 fila de %d campos y hay %d filas' % (campos, len(filas)))
        return filas[0]

    def columnas_rel(self):
        """Las dos columnas de ai_provider_role_rel, leídas del catálogo."""
        if self._rel is None:
            cols = [f[0] for f in self.ejecutar(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'ai_provider_role_rel' ORDER BY 1;")]
            rol = [c for c in cols if 'role' in c]
            prov = [c for c in cols if c not in rol]
            if len(cols) != 2 or len(rol) != 1 or len(prov) != 1 \
                    or not all(RE_COLUMNA.match(c) for c in cols):
                raise ErrorSQL('ai_provider_role_rel no tiene las dos columnas previstas (%d)' % len(cols))
            self._rel = (prov[0], rol[0])
        return self._rel

    def design(self):
        """(proveedor activo, proveedor con el rol design)."""
        prov, rol = self.columnas_rel()
        f = self.una(
            "SELECT (SELECT count(*) FROM ai_provider WHERE id = %(p)d AND active), "
            "(SELECT count(*) FROM ai_provider_role_rel x JOIN ai_provider_role r ON r.id = x.%(rol)s "
            "WHERE x.%(prov)s = %(p)d AND r.code = 'design');"
            % {'p': PROVEEDOR_P34, 'rol': rol, 'prov': prov}, 2)
        return f[0] == '1', int(f[1]) >= 1

    def ahora(self):
        marca = self.una("SELECT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS');", 1)[0]
        if not RE_MARCA_TIEMPO.match(marca):
            raise ErrorSQL('marca de tiempo no válida')
        return marca

    def no_page(self, desde, motivo=''):
        """Filas «No page was built: <motivo>…» de ai_log desde el inicio del turno."""
        if not RE_MARCA_TIEMPO.match(desde) or "'" in motivo:
            raise ErrorSQL('parámetros no válidos')
        return int(self.una(
            "SELECT count(*) FROM ai_log WHERE create_date >= '%s' "
            "AND result_summary LIKE 'No page was built: %s%%';" % (desde, motivo), 1)[0])

    def motivos(self, desde):
        """Motivo de cada «No page was built» desde la marca, clasificado (sin texto libre)."""
        if not RE_MARCA_TIEMPO.match(desde):
            raise ErrorSQL('parámetros no válidos')
        casos = ' '.join("WHEN result_summary LIKE 'No page was built: %s%%' THEN '%s'" % (t, e)
                         for t, e in MOTIVOS_FIJOS)
        filas = self.ejecutar(
            "SELECT CASE %s WHEN result_summary LIKE 'No page was built: the design call broke: %%' "
            "THEN 'la llamada a Design falló' "
            "WHEN substring(result_summary FROM '^No page was built: ([A-Za-z_.]*(Error|Exception))') "
            "IS NOT NULL THEN 'excepción ' || substring(result_summary FROM "
            "'^No page was built: ([A-Za-z_.]*(Error|Exception))') "
            "WHEN result_summary ~* 'timed? ?out|timeout' THEN 'timeout' ELSE 'otro' END "
            "FROM ai_log WHERE create_date >= '%s' AND result_summary LIKE 'No page was built%%' "
            "ORDER BY id;" % (casos, desde))
        return [f[0] for f in filas if f]

    def page_tab(self, desde):
        """(filas domain_index, alguna con page_tab) desde la marca."""
        if not RE_MARCA_TIEMPO.match(desde):
            raise ErrorSQL('parámetros no válidos')
        f = self.una(
            "SELECT count(*), coalesce(bool_or(position('page_tab' IN coalesce(result_summary, '') "
            "|| coalesce(result_data, '') || coalesce(additional_info, '')) > 0), false) "
            "FROM ai_log WHERE create_date >= '%s' AND flow = 'domain_index';" % desde, 2)
        return int(f[0]), _t(f[1])

    def sesion(self, sid):
        filas = self.ejecutar(
            "SELECT coalesce(canvas_rev, 0), coalesce(canvas_design, '') <> '', "
            "position(%s IN coalesce(canvas_design, '')) > 0, "
            "position(%s IN coalesce(canvas_design, '')) > 0, "
            "position(%s IN coalesce(canvas_design, '')) > 0, coalesce(user_id, 0) "
            "FROM chatboo_session WHERE id = %d;"
            % (HOSTIL_SQL, ESCAPADO_SQL, ESCAPADO_TABLA_SQL, int(sid)))
        if len(filas) != 1 or len(filas[0]) != 6:
            return None
        f = filas[0]
        return {'rev': int(f[0]), 'lienzo': _t(f[1]), 'cierra_script': _t(f[2]),
                'escapado': _t(f[3]), 'escapado_tabla': _t(f[4]), 'uid': int(f[5])}

    def mensaje(self, sid):
        """El último mensaje guardado de la sesión, en booleanos."""
        notas = ' OR '.join("position('%s' IN c) > 0" % n for n in NOTAS_P34.values())
        finales = ' OR '.join("right(rtrim(c), %d) = '%s'" % (len(n), n) for n in NOTAS_P34.values())
        filas = self.ejecutar(
            "WITH u AS (SELECT (nullif(messages, '')::jsonb) -> -1 AS m FROM chatboo_session WHERE id = %d), "
            "v AS (SELECT m, coalesce(m ->> 'content', '') AS c FROM u) "
            "SELECT coalesce(m ->> 'role', '') = 'assistant', (%s), "
            "c = coalesce(m ->> 'original_content', ''), coalesce(m ->> 'is_error', '') = 'true', "
            "(%s), left(ltrim(c), 1) = '<' FROM v WHERE m IS NOT NULL;"
            % (int(sid), notas, finales))
        if len(filas) != 1 or len(filas[0]) != 6:
            return None
        f = filas[0]
        return {'asistente': _t(f[0]), 'aviso': _t(f[1]), 'iguales': _t(f[2]),
                'error': _t(f[3]), 'al_final': _t(f[4]), 'html': _t(f[5])}

    def contacto(self):
        """Contactos activos de D23 («Seges P34 …» con el cierre de script)."""
        return int(self.una(
            "SELECT count(*) FROM res_partner WHERE active AND name LIKE 'Seges P34 %%' "
            "AND position(%s IN name) > 0;" % HOSTIL_SQL, 1)[0])

    def plantada(self):
        """Sesiones plantadas (D24): lista de (id, canvas_rev, uid, canvas_open)."""
        filas = self.ejecutar(
            "SELECT id, coalesce(canvas_rev, 0), coalesce(user_id, 0), coalesce(canvas_open, false) "
            "FROM chatboo_session WHERE name = '%s' ORDER BY id;" % NOMBRE_PLANTADA)
        return [(int(f[0]), int(f[1]), int(f[2]), _t(f[3])) for f in filas if len(f) == 4]


def sqlprueba(consultas=None):
    """Cada consulta del escenario contra la BD real, en solo lectura."""
    q = consultas or Consultas()
    fallos = 0
    pruebas = (
        ('columnas de ai_provider_role_rel', lambda: 'dos columnas' if q.columnas_rel() else ''),
        ('proveedor %d' % PROVEEDOR_P34, lambda: 'activo %s, design %s' % tuple(
            'sí' if v else 'no' for v in q.design())),
        ('hora del servidor', lambda: 'leída' if q.ahora() else ''),
        ('ai_log «No page was built» desde ahora', lambda: '%d filas' % q.no_page(q.ahora())),
        ('motivos de «No page was built» desde ahora', lambda: '%d' % len(q.motivos(q.ahora()))),
        ('page_tab en domain_index desde ahora', lambda: '%d filas' % q.page_tab(q.ahora())[0]),
        ('sesión inexistente', lambda: 'sin fila' if q.sesion(0) is None else 'CON FILA'),
        ('último mensaje de una sesión inexistente',
         lambda: 'sin fila' if q.mensaje(0) is None else 'CON FILA'),
        ('contacto hostil (D23)', lambda: '%d' % q.contacto()),
        ('sesión plantada (D24)', lambda: '%d' % len(q.plantada())),
    )
    for nombre, f in pruebas:
        try:
            print('  %-45s OK (%s)' % (nombre, f()))
        except ErrorSQL as e:
            fallos += 1
            print('  %-45s FALLA: %s' % (nombre, e))
    try:
        ids = [p[0] for p in q.plantada()]
        for sid in ids[:1]:
            s, m = q.sesion(sid), q.mensaje(sid)
            print('  %-45s OK (sesión %d: rev %d, cierra_script %s; mensajes: %s)' % (
                'lectura de la sesión plantada', sid, s['rev'], 'sí' if s['cierra_script'] else 'no',
                'ninguno' if m is None else 'sí'))
    except (ErrorSQL, TypeError) as e:
        fallos += 1
        print('  %-45s FALLA: %s' % ('lectura de la sesión plantada', e))
    print('Consultas del escenario p34: %s' % ('todas OK' if not fallos else '%d FALLA' % fallos))
    return OK if not fallos else NO_CONFIRMADO


# -- el chat ---------------------------------------------------------------
# Componente en window.__chatboo_component (chatboo_systray.js:498); se abre
# con el bus chatboo_overlay_show (chatboo_systray.js:39). El texto se lee del
# textarea (_promptText, chatboo_component_v2.js:3562) y se envía con
# _sendMessage (:3043). Burbujas: .o_chatboo_message[data-ai-generated=true]
# con su .o_chatboo_content (:5887 y :6034).
# El componente solo existe cuando la bandeja ha recibido el evento
# (chatboo_systray.js:39 y :498), y la bandeja solo lo escucha desde su start(),
# que es también cuando aparece .o_chatboo_systray_item. Tras recargar, un
# evento lanzado antes se pierde (L2, 17/11/2026): se espera a la bandeja y se
# relanza cada %(relanzar)d ms hasta que aparezca el componente. Si la bandeja no
# aparece en %(sin_bandeja)d ms, se lanza igualmente.
CHAT_ABRIR_JS = r"""(async () => {
  const inicio = Date.now(), fin = inicio + %(espera)d * 1000;
  let ultimo = 0, lanzados = 0;
  while (Date.now() < fin) {
    const c = window.__chatboo_component;
    if (c && c.state && document.querySelector('textarea.o_chatboo_prompt')) return 'ok';
    const lista = document.readyState === 'complete'
      && (document.querySelector('.o_chatboo_systray_item') || Date.now() - inicio > %(sin_bandeja)d);
    if (lista && !c && Date.now() - ultimo >= %(relanzar)d) {
      try {
        const core = window.odoo && odoo.__DEBUG__ && odoo.__DEBUG__.services
          && odoo.__DEBUG__.services['web.core'];
        if (core && core.bus) { core.bus.trigger('chatboo_overlay_show', {}); ultimo = Date.now(); lanzados++; }
      } catch (e) {}
    }
    await new Promise(r => setTimeout(r, 300));
  }
  if (window.__chatboo_component) return 'sin-cuadro';
  if (!document.querySelector('.o_chatboo_systray_item')) return 'sin-bandeja (eventos lanzados: ' + lanzados + ')';
  return 'sin-componente (eventos lanzados: ' + lanzados + ')';
})()"""
ESPERA_CHAT = 60  # segundos para que el chat se abra
RELANZAR_MS = 5000
SIN_BANDEJA_MS = 15000
CHAT_NUEVA_JS = ("(async () => { const c = window.__chatboo_component;"
                 " await c._createNewSession(true); return c.state.currentSessionId || 0; })()")
CHAT_SELECCIONAR_JS = ("(async () => { const c = window.__chatboo_component;"
                       " await c._selectSession(%d); return c.state.currentSessionId || 0; })()")
CHAT_ENVIAR_JS = r"""(() => {
  const c = window.__chatboo_component, el = document.querySelector('textarea.o_chatboo_prompt');
  if (!c || !el) return 'sin-chat';
  el.value = %s;
  c.state.currentInput = el.value;
  el.dispatchEvent(new Event('input', {bubbles: true}));
  c._sendMessage();
  return 'ok';
})()"""
CHAT_ESTADO_JS = r"""(() => {
  const c = window.__chatboo_component;
  return {
    pensando: !!(c && c.state && c.state.thinking),
    sid: (c && c.state && c.state.currentSessionId) || 0,
    burbujas: document.querySelectorAll('.o_chatboo_message[data-ai-generated=true]').length,
  };
})()"""
CHAT_MEDIR_JS = r"""(() => {
  const notas = %s;
  const todas = document.querySelectorAll('.o_chatboo_message[data-ai-generated=true]');
  const r = {burbujas: todas.length, presente: false, cursiva: false, guiones: false,
             etiquetas: false, al_final: false};
  if (!todas.length) return r;
  const b = todas[todas.length - 1];
  const cont = b.querySelector('.o_chatboo_content') || b;
  const t = cont.textContent || '';
  for (const n of notas) {
    if (t.indexOf(n) < 0) continue;
    r.presente = true;
    r.guiones = r.guiones || t.indexOf('_' + n + '_') >= 0;
    r.cursiva = r.cursiva || Array.from(cont.querySelectorAll('em, i')).some(e => e.textContent.indexOf(n) >= 0);
    r.al_final = r.al_final || t.trim().endsWith(n);
  }
  r.etiquetas = r.presente && /<\/?(em|p)>/.test(t);
  return r;
})()"""


class ErrorChat(Exception):
    """El chat no se pudo abrir o manejar."""


# Fallo del proveedor que no deja is_error (L2, 17/11/2026: timeout de Gemini;
# engine_tool_loop da ERROR, agent_engine WARNING de failover y la respuesta se
# guarda como un mensaje normal). Se cuenta en el log del servidor; nunca se
# imprime el mensaje (la línea lleva la URL del proveedor).
RE_MOTOR = re.compile(
    r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ \d+ (ERROR|CRITICAL|WARNING) (\S+) '
    r'odoo\.addons\.pns_ai_mcp\.')


def contar_motor(texto, desde):
    """(errores, avisos) de pns_ai_mcp en BD desde la marca UTC «desde»."""
    errores = avisos = 0
    for linea in texto.splitlines():
        m = RE_MOTOR.search(linea)
        if not m or m.group(3) != BD or m.group(1) < desde:
            continue
        if m.group(2) == 'WARNING':
            avisos += 1
        else:
            errores += 1
    return errores, avisos


def motor_en_vivo(desde):
    """contar_motor sobre `odoo-dev 14 log all` (el mismo log que usa C)."""
    salida = subprocess.run(
        ['odoo-dev', '14', 'log', 'all'], cwd=LAB,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=120,
    ).stdout
    return contar_motor(salida.decode('utf-8', 'replace'), desde)


def pausa_terminal(ch, texto):
    return ch.esperar_linea('\n>>> %s\n>>> Pulsa Intro cuando esté hecho: ' % texto) is not None


def repetir_terminal(ch, texto, pregunta='Repetir el paso'):
    if pregunta == 'Continuar':
        return (ch.esperar_linea('\n>>> %s (s/N) ' % texto) or '').strip() == 's'
    return (ch.esperar_linea('\n>>> %s ¿%s? (s/N) ' % (texto, pregunta)) or '').strip() == 's'


def _si(valor):
    return 'sí' if valor else 'no'


class EscenarioP34:
    def __init__(self, ch, base, salida, uid, consultas, pausa, repetir, espera_turno,
                 motor=motor_en_vivo, continuar=None):
        self.ch, self.base, self.salida, self.uid = ch, base, salida, uid
        self.motor = motor
        self.continuar = continuar or (lambda ch, texto: repetir_terminal(ch, texto, 'Continuar'))
        self.fallos_seguidos = 0
        self.cortado = False
        self.q, self.pausa, self.repetir = consultas, pausa, repetir
        self.espera_turno = espera_turno
        self.resultados = []  # (paso, 'OK' | 'INCIDENCIA' | 'NO CONCLUYENTE' | 'NO CONFIRMADO', motivo)
        self.design_quitado = False

    # -- utilidades --------------------------------------------------------
    def anotar(self, paso, resultado, motivo=''):
        self.resultados.append((paso, resultado, motivo))
        print('  => %s: %s%s' % (paso, resultado, (' (%s)' % motivo) if motivo else ''))

    def abrir_chat(self, recargar=False):
        if recargar or not self.ch.evaluar('!!window.__chatboo_component'):
            if recargar or not self.ch.evaluar("location.pathname === '/web'"):
                err = self.ch.ir(self.base + '/web')
                if err:
                    raise ErrorChat('no carga /web: ' + err)
        r = self.ch.evaluar(CHAT_ABRIR_JS % {
            'espera': ESPERA_CHAT, 'relanzar': RELANZAR_MS, 'sin_bandeja': SIN_BANDEJA_MS},
            promesa=True, espera=ESPERA_CHAT + 30)
        if r != 'ok':
            raise ErrorChat('el chat no se abre (%s)' % r)

    def esperar_quieto(self, espera, burbujas_antes=None):
        """True cuando el chat deja de pensar (y, si se pide, hay burbuja nueva)."""
        fin = time.time() + espera
        visto, quieto_desde = burbujas_antes is None, None
        while time.time() < fin:
            e = self.ch.evaluar(CHAT_ESTADO_JS)
            if burbujas_antes is not None and (e['pensando'] or e['burbujas'] > burbujas_antes):
                visto = True
            if visto and not e['pensando'] and (
                    burbujas_antes is None or e['burbujas'] > burbujas_antes):
                quieto_desde = quieto_desde or time.time()
                # En vivo, tras «done» el cliente puede recargar la sesión
                # (chatboo_component_v2.js:3230-3238): se espera a que asiente.
                if time.time() - quieto_desde >= ASIENTO:
                    return True
            else:
                quieto_desde = None
            self.ch.bombear(SONDEO)
        return False

    def medir(self, etiqueta, paso):
        m = self.ch.evaluar(CHAT_MEDIR_JS % json.dumps(sorted(NOTAS_P34.values())))
        m['clase'] = clase_pintado(m)
        png = 'p34_%s_%s.png' % (nombre_archivo(paso), etiqueta)
        self.ch.captura(os.path.join(self.salida, png))
        print('  burbuja %-14s aviso %s; clase: %s; al final: %s; captura: %s' % (
            {'vivo': 'en vivo:', 'recarga': 'tras recargar:'}[etiqueta], _si(m['presente']),
            m['clase'], _si(m['al_final']) if m['presente'] else '-', png))
        return m

    def ver_lienzo(self, sid, paso):
        """Abre el lienzo de la sesión y cuenta los alert() que lanza."""
        antes = self.ch.alertas
        self.ch.nueva_medida('p34 %s lienzo' % paso)
        err = self.ch.ir(self.base + '/chatboo/canvas/%d' % sid)
        self.ch.bombear(ESPERA_PINTADO)
        n = self.ch.alertas - antes
        png = 'p34_%s_lienzo.png' % nombre_archivo(paso)
        self.ch.captura(os.path.join(self.salida, png))
        print('  lienzo /chatboo/canvas/%d: carga %s; alert(): %d; captura: %s' % (
            sid, err or 'ok', n, png))
        return n

    def turno(self, paso, sid=None):
        """Un turno real. Devuelve un diccionario de medidas (sin contenidos)."""
        print('\n== p34 %s' % paso)
        self.ch.nueva_medida('p34 ' + paso)
        self.abrir_chat()
        if sid is None:
            sid = self.ch.evaluar(CHAT_NUEVA_JS, promesa=True, espera=60)
            if not sid:
                raise ErrorChat('no se creó la sesión nueva')
        else:
            if self.ch.evaluar(CHAT_SELECCIONAR_JS % sid, promesa=True, espera=60) != sid:
                raise ErrorChat('no se pudo volver a la sesión %d' % sid)
        self.esperar_quieto(60)
        antes = self.ch.evaluar(CHAT_ESTADO_JS)
        previa = self.q.sesion(sid)
        r = {'sid': sid, 'desde': self.q.ahora(), 'alertas': self.ch.alertas, 'fin': False,
             'vivo': None, 'recarga': None, 'rev_antes': previa['rev'] if previa else 0}
        print('  sesión %d; mensaje %s enviado (%d caracteres)' % (
            sid, paso, len(MENSAJES_P34[paso])))
        if self.ch.evaluar(CHAT_ENVIAR_JS % json.dumps(MENSAJES_P34[paso])) != 'ok':
            raise ErrorChat('no se pudo escribir en el chat')
        inicio = time.time()
        r['fin'] = self.esperar_quieto(self.espera_turno, antes['burbujas'])
        print('  fin del turno: %s (%d s)' % (_si(r['fin']), time.time() - inicio))
        try:
            if r['fin']:
                r['vivo'] = self.medir('vivo', paso)
                self.abrir_chat(recargar=True)
                if self.ch.evaluar(CHAT_SELECCIONAR_JS % sid, promesa=True, espera=60) != sid:
                    raise ErrorChat('tras recargar no se pudo volver a la sesión %d' % sid)
                self.esperar_quieto(60)
                r['recarga'] = self.medir('recarga', paso)
        except ErrorChat:
            # El mensaje ya se envió: el SQL y el log del turno se imprimen antes de abortar.
            print('  (el chat falló tras enviar el mensaje; SQL y log del turno antes de abortar)')
            self.informe(r, paso)
            raise
        self.informe(r, paso)
        return r

    def informe(self, r, paso):
        """SQL de la sesión y del último mensaje, log del motor y alert() del turno."""
        sid = r['sid']
        r['alertas'] = self.ch.alertas - r['alertas']
        r['s'] = self.q.sesion(sid)
        r['m'] = self.q.mensaje(sid)
        r['no_page'] = self.q.no_page(r['desde'])
        r['motivos'] = self.q.motivos(r['desde']) if r['no_page'] else []
        r['page_tab'] = self.q.page_tab(r['desde'])
        try:
            r['motor'] = self.motor(r['desde'])
        except (OSError, subprocess.SubprocessError) as err:
            r['motor'] = None
            print('  log del motor: no se pudo leer (%s)' % err.__class__.__name__)
        s, m = r['s'], r['m']
        if s:
            print('  SQL sesión: canvas_rev %d; cierra_script %s; escapado %s; escapado en tabla %s'
                  % (s['rev'], _si(s['cierra_script']), _si(s['escapado']), _si(s['escapado_tabla'])))
        if m:
            print('  SQL último mensaje: del asistente %s; con aviso %s; aviso al final %s; '
                  'original_content = content %s; empieza por < %s; de error %s' % (
                      _si(m['asistente']), _si(m['aviso']), _si(m['al_final']) if m['aviso'] else '-',
                      _si(m['iguales']), _si(m['html']), _si(m['error'])))
        print('  SQL ai_log: «No page was built…» desde el inicio del turno: %d%s' % (
            r['no_page'], (' (motivo: %s)' % ', '.join(r['motivos'])) if r['motivos'] else ''))
        print('  SQL ai_log: paquete page_tab activado en el turno: %s (%d filas domain_index)' % (
            _si(r['page_tab'][1]), r['page_tab'][0]))
        if r['motor'] is not None:
            print('  log del motor (pns_ai_mcp) desde el inicio del turno: %d ERROR, %d WARNING'
                  % r['motor'])
        print('  alert() durante el turno: %d' % r['alertas'])
        medida = self.ch.medida
        print('  errores de JS: %d (textos en detalle.txt)' % (
            medida['errores_log'] + medida['errores_consola'] + medida['excepciones_js']))

    def turno_con_repeticion(self, paso, sid=None):
        """Repite una vez, si Sergio quiere, un turno sin fin o con error del proveedor."""
        r = self.turno(paso, sid)
        if self.fallo_proveedor(r) and self.repetir(
                self.ch, '%s: %s.' % (paso, self.fallo_proveedor(r))):
            r = self.turno(paso, r['sid'])
        self.fallos_seguidos = self.fallos_seguidos + 1 if self.fallo_proveedor(r) else 0
        return r

    def cortar(self, paso):
        """True si el paso no se ejecuta porque el proveedor sigue cayéndose.

        Tras FALLOS_PARA_PREGUNTAR pasos seguidos que fallan por el proveedor
        (ya repetidos), se pregunta si se sigue (17/11/2026: diez turnos de
        49 s sin poder probar nada). Con «no», los pasos que quedan se anotan
        como no ejecutados y se va a la limpieza.
        """
        if not self.cortado and self.fallos_seguidos >= FALLOS_PARA_PREGUNTAR:
            seguir = self.continuar(self.ch, (
                'El proveedor ha fallado en %d pasos seguidos. ¿Continuar con los pasos que quedan?'
                % self.fallos_seguidos))
            self.fallos_seguidos = 0
            self.cortado = not seguir
        if self.cortado:
            print('\n== p34 %s' % paso)
            self.anotar(paso, 'NO EJECUTADO', 'proveedor caído')
        return self.cortado

    @staticmethod
    def fallo_proveedor(r):
        if not r['fin']:
            return 'el turno no terminó en el tiempo de espera'
        if not r['s'] or not r['m'] or not r['m']['asistente']:
            return 'no hay respuesta guardada del asistente'
        if r['m']['error']:
            return 'el proveedor devolvió un error (429 o 503, por ejemplo)'
        # Errores del motor que no dejan is_error: solo cuentan si el turno no
        # dejó huella en la página (ni rechazo ni cambio de canvas_rev). Un
        # error del que el motor se recupera no anula un turno que sí la deja.
        errores = (r.get('motor') or (0, 0))[0]
        if errores and not r['no_page'] and r['s']['rev'] == r['rev_antes']:
            return 'falló el proveedor (%d líneas ERROR del motor en el log)' % errores
        return ''

    @staticmethod
    def sin_page_tab(r):
        return '' if r['page_tab'][1] else '; el paquete page_tab no se activó'

    @staticmethod
    def aviso_bien(r):
        """Aviso presente y sin marcas, en vivo y tras recargar, y bien guardado."""
        return (r['m']['aviso'] and r['m']['iguales'] and r['m']['al_final']
                and all(r[k]['presente'] and r[k]['clase'] == 'línea llana' and r[k]['al_final']
                        for k in ('vivo', 'recarga')))

    @staticmethod
    def sin_aviso(r):
        return not r['m']['aviso'] and not r['vivo']['presente'] and not r['recarga']['presente']

    def confirmar(self, texto, comprobar):
        """Pausa hasta que el SQL confirme lo pedido. comprobar() → (bien, línea)."""
        for intento in range(1, INTENTOS_PAUSA + 1):
            if not self.pausa(self.ch, texto):
                print('  pausa: sin respuesta en la terminal')
                return False
            bien, linea = comprobar()
            print('  SQL: %s (intento %d de %d)' % (linea, intento, INTENTOS_PAUSA))
            if bien:
                return True
        return False

    def ver_design(self, quiere, con_contacto=False):
        activo, design = self.q.design()
        linea = 'proveedor %d activo %s; con «Design» %s' % (PROVEEDOR_P34, _si(activo), _si(design))
        bien = activo and design == quiere
        if con_contacto:
            n = self.q.contacto()
            linea += '; contactos de D23 activos: %d' % n
            bien = bien and n == 1
        return bien, linea

    # -- pasos -------------------------------------------------------------
    def rechazo(self, paso, sid, motivo):
        """T1 y T1b: el lienzo rechaza la página y la burbuja lleva el aviso."""
        r = self.turno_con_repeticion(paso, sid)
        fallo = self.fallo_proveedor(r)
        if fallo:
            self.anotar(paso, 'NO CONCLUYENTE', fallo)
            return r
        n = self.q.no_page(r['desde'], motivo)
        print('  SQL ai_log: «No page was built: %s…» desde el inicio del turno: %d' % (motivo, n))
        if not n:
            self.anotar(paso, 'NO CONCLUYENTE', 'el modelo no pidió la página: no hubo rechazo'
                        + self.sin_page_tab(r))
        elif r['s']['rev'] == 0 and self.aviso_bien(r):
            self.anotar(paso, 'OK', 'rechazo con aviso en línea llana, en vivo y tras recargar')
        else:
            self.anotar(paso, 'INCIDENCIA', 'hubo rechazo y el aviso o canvas_rev no son los previstos')
        return r

    def ejecutar(self):
        q = self.q
        print('\n== p34 paso 0: condiciones (SQL de solo lectura)')
        activo, design = q.design()
        contactos, plantadas = q.contacto(), q.plantada()
        print('  proveedor %d: activo %s; con «Design» %s' % (PROVEEDOR_P34, _si(activo), _si(design)))
        print('  contactos de D23 activos: %d (se crea en la primera pausa)' % contactos)
        print('  sesiones plantadas (D24): %d (previsto 1)' % len(plantadas))
        bien = activo and design and contactos <= 1 and len(plantadas) == 1
        if len(plantadas) == 1:
            pid, prev, puid, pabierta = plantadas[0]
            print('  sesión plantada %d: canvas_rev %d; del usuario de la sesión %s; lienzo abierto %s'
                  % (pid, prev, _si(puid == self.uid), _si(pabierta)))
            bien = bien and prev >= 1 and puid == self.uid and pabierta
        if not bien:
            self.anotar('paso 0', 'NO CONFIRMADO', 'faltan condiciones: no se envía ningún turno')
            return

        print('\n== p34 paso 1: contacto de D23 y quitar «Design» (pausa)')
        self.ch.abrir_admin(self.base + '/web/login?db=' + BD)
        self.design_quitado = True
        if not self.confirmar((
                'En la SEGUNDA ventana de Chrome: (1) entra como administrador; (2) crea el contacto '
                'de D23 con el nombre de la guía, si no existe ya; (3) abre el proveedor %d (Gemini '
                'lab), quita el rol «Design» y guarda.' % PROVEEDOR_P34),
                lambda: self.ver_design(False, con_contacto=True)):
            self.anotar('paso 1', 'NO CONFIRMADO', 'falta el contacto de D23 o «Design» sigue puesto')
            return

        t1 = self.rechazo('T1', None, MOTIVO_SIN_DESIGN)
        if not self.cortar('T1b'):
            self.rechazo('T1b', t1['sid'], MOTIVO_SIN_DESIGN)

        if not self.cortado:
            print('\n== p34 paso 4: volver a marcar «Design» (pausa)')
            if not self.restaurar_design():
                return

        if not self.cortar('V2'):
            paso = 'V2'
            r = self.turno_con_repeticion(paso, t1['sid'])
            fallo = self.fallo_proveedor(r)
            if fallo:
                self.anotar(paso, 'NO CONCLUYENTE', fallo)
            else:
                n = q.no_page(r['desde'])
                print('  SQL ai_log: «No page was built…» desde el inicio del turno: %d' % n)
                if r['s']['rev'] >= 1 and self.sin_aviso(r):
                    self.anotar(paso, 'OK', 'página creada y burbuja sin aviso')
                elif r['s']['rev'] >= 1:
                    self.anotar(paso, 'INCIDENCIA', 'la página cambió y la burbuja lleva el aviso')
                else:
                    self.anotar(paso, 'NO CONCLUYENTE', 'no se creó la página (canvas_rev 0)'
                                + self.sin_page_tab(r))

        r5, rev5 = None, 0
        if not self.cortar('5b′'):
            paso = '5b′'
            r5 = self.turno_con_repeticion(paso)
            fallo = self.fallo_proveedor(r5)
            if fallo:
                self.anotar(paso, 'NO CONCLUYENTE', fallo)
            elif r5['s']['rev'] < 1:
                self.anotar(paso, 'NO CONCLUYENTE', 'no se creó la página (canvas_rev 0)'
                            + self.sin_page_tab(r5))
            else:
                rev5 = r5['s']['rev']
                self.juzgar_hostil(paso, r5, self.ver_lienzo(r5['sid'], paso))

        if not self.cortar('6c'):
            paso = '6c'
            if not rev5:
                print('\n== p34 %s' % paso)
                self.anotar(paso, 'NO CONCLUYENTE', '5b′ no dejó página que cambiar')
            else:
                r = self.turno_con_repeticion(paso, r5['sid'])
                fallo = self.fallo_proveedor(r)
                if fallo:
                    self.anotar(paso, 'NO CONCLUYENTE', fallo)
                elif r['s']['rev'] > rev5:
                    self.juzgar_hostil(paso, r, self.ver_lienzo(r['sid'], paso))
                elif r['s']['cierra_script'] or r['alertas']:
                    self.anotar(paso, 'INCIDENCIA', 'valor hostil en crudo o alert()')
                else:
                    n = q.no_page(r['desde'])
                    print('  SQL ai_log: «No page was built…» desde el inicio del turno: %d' % n)
                    self.anotar(paso, 'NO CONCLUYENTE', 'canvas_rev no subió (%s)' % (
                        'rechazo, con aviso %s' % _si(r['m']['aviso']) if n else 'el modelo no cambió la página'))

        if not self.cortar('6d′'):
            self.paso_6d(plantadas[0][0])

    def juzgar_hostil(self, paso, r, alertas_lienzo):
        s = r['s']
        if s['cierra_script'] or alertas_lienzo or r['alertas']:
            self.anotar(paso, 'INCIDENCIA', 'valor hostil en crudo o alert()')
        elif not self.sin_aviso(r):
            self.anotar(paso, 'INCIDENCIA', 'la página cambió y la burbuja lleva el aviso')
        elif s['escapado'] or s['escapado_tabla']:
            self.anotar(paso, 'OK', 'canvas_rev %d; valor hostil escapado; sin alert() ni aviso' % s['rev'])
        else:
            self.anotar(paso, 'NO CONCLUYENTE', 'el valor hostil no está en la página')

    def paso_6d(self, pid):
        paso = '6d′'
        print('\n== p34 %s: control del lienzo plantado (sesión %d)' % (paso, pid))
        control = self.ver_lienzo(pid, paso + ' control')
        # Informativo (17/11/2026): el lienzo se sirve en un iframe con sandbox y la
        # <meta> CSP del parche 27; 6d′ mide el rechazo del servidor, no el alert().
        print('  control (informativo): alert() del lienzo plantado: %d' % control)
        antes = self.q.sesion(pid)
        for intento in range(1, INTENTOS_6D + 1):
            print('\n-- 6d′, intento %d de %d' % (intento, INTENTOS_6D))
            r = self.turno(paso, pid)
            fallo = self.fallo_proveedor(r)
            n = 0 if not r['fin'] else self.q.no_page(r['desde'], MOTIVO_MARCADO)
            print('  SQL ai_log: «No page was built: %s» desde el inicio del turno: %d'
                  % (MOTIVO_MARCADO, n))
            ultimo = intento == INTENTOS_6D
            if not fallo and r['s']['rev'] != antes['rev']:
                if r['s']['cierra_script']:
                    self.anotar(paso, 'INCIDENCIA', 'la página cambió y conserva el valor en crudo')
                else:
                    self.anotar(paso, 'NO CONCLUYENTE',
                                'la página se sustituyó sin el valor en crudo: no hubo rechazo')
                return
            if not fallo and n:
                if self.aviso_bien(r):
                    self.anotar(paso, 'OK', 'rechazo por valor en crudo, canvas_rev igual y aviso en línea llana')
                else:
                    self.anotar(paso, 'INCIDENCIA', 'hubo rechazo y el aviso no es el previsto')
                return
            if not fallo and r['no_page']:
                # Rechazo por otro motivo (17/11/2026: un timeout): el aviso se juzga
                # igual, pero no es el rechazo por valor en crudo que busca 6d′.
                otro = ', '.join(r['motivos']) or 'sin clasificar'
                if not self.aviso_bien(r) or r['s']['rev'] != antes['rev']:
                    self.anotar(paso, 'INCIDENCIA',
                                'rechazo por otro motivo (%s) y el aviso o canvas_rev no son los previstos' % otro)
                    return
                texto = ('rechazo por otro motivo (%s): aviso en línea llana correcto, pero no es el '
                         'rechazo por valor en crudo de 6d′' % otro)
                print('  %s' % texto)
                if ultimo or not self.repetir(self.ch, '6d′: %s.' % texto):
                    self.anotar(paso, 'NO CONCLUYENTE', texto)
                    return
                continue
            if ultimo:
                self.anotar(paso, 'NO CONCLUYENTE', fallo or 'el modelo no cambió la página: no hubo rechazo')

    def restaurar_design(self):
        ok = self.confirmar((
            'En la SEGUNDA ventana de Chrome: vuelve a marcar el rol «Design» en el proveedor %d '
            'y guarda.' % PROVEEDOR_P34), lambda: self.ver_design(True))
        if ok:
            self.design_quitado = False
        else:
            self.anotar('paso 4', 'NO CONFIRMADO', '«Design» no está en el proveedor')
        return ok

    def limpieza(self):
        """«Design» marcado y contacto de D23 archivado, pase lo que pase antes."""
        if not self.ch.admin:
            return
        print('\n== p34 limpieza: «Design» marcado y contacto de D23 archivado')
        try:
            if self.design_quitado:
                self.restaurar_design()
            if self.q.contacto() > 0:
                def archivado():
                    n = self.q.contacto()
                    return n == 0, 'contactos de D23 activos: %d' % n
                if not self.confirmar('En la SEGUNDA ventana de Chrome: archiva el contacto de D23 '
                                      '(Acción → Archivar).', archivado):
                    self.anotar('limpieza', 'NO CONFIRMADO', 'el contacto de D23 sigue activo')
            else:
                print('  SQL: contactos de D23 activos: 0')
        except (ErrorSQL, ErrorCDP) as err:
            print('  no se pudo confirmar: %s' % err)
            self.anotar('limpieza', 'NO CONFIRMADO', 'limpieza sin confirmar por SQL')
        if self.design_quitado:
            print('  ATENCIÓN: «Design» NO está confirmado en el proveedor %d. Márcalo a mano y '
                  'compruébalo con la orden «sqlprueba».' % PROVEEDOR_P34)
            self.anotar('limpieza', 'NO CONFIRMADO', '«Design» sin restaurar')
        self.ch.cerrar_admin()

    def codigo(self):
        clases = {r for _p, r, _m in self.resultados}
        print('\n== p34 resumen')
        for paso, resultado, motivo in self.resultados:
            print('  %-7s %-15s %s' % (paso, resultado, motivo))
        incid = [('p34', p) for p, r, _m in self.resultados if r == 'INCIDENCIA']
        return incid, 'NO CONFIRMADO' in clases, bool(clases & {'NO CONCLUYENTE', 'NO EJECUTADO'})


def escenario_p34(ch, base, salida, uid, consultas, pausa, repetir, espera_turno,
                  motor=motor_en_vivo, continuar=None):
    """Devuelve (incidencias, no confirmado, no concluyente)."""
    e = EscenarioP34(ch, base, salida, uid, consultas, pausa, repetir, espera_turno, motor=motor,
                     continuar=continuar)
    try:
        e.ejecutar()
    except (ErrorSQL, ErrorChat) as err:
        print('  ABORTADO el escenario: %s' % err)
        e.anotar('escenario', 'NO CONFIRMADO', 'interrumpido: ver la línea anterior')
    finally:
        # «Design» no se deja quitado ni el contacto activo, aunque algo falle.
        e.limpieza()
    return e.codigo()


# --------------------------------------------------------------------------
# Escenario tarjeta (D47, 17/11/2026): reintento tras un rechazo too_soon
# --------------------------------------------------------------------------
# Lo que mide (lectura de código, rama 14.0-pns-ai-3973):
# - la tarjeta se pinta al abrir el panel: chatboo_systray.js:409-411 →
#   _restorePendingVerifications (chatboo_component_v2.js:2162-2188) →
#   /verification/pending sin peek, que genera el token y empieza los 5 s del
#   servidor (verification_ui.py:142-152; safe_operation.py:564-596 y :2076-2097);
# - una tarjeta high deja Confirmar deshabilitado 5 s desde que se pinta
#   (chatboo_component_v2.js:2373-2393): el clic antes de 5 s es FORZADO (se
#   quita «disabled» y se lanza click() sobre el botón; pasa por el manejador
#   normal, :2494). Una persona no puede hacerlo;
# - con too_soon, _retryRefusedCard (chatboo_component_v2.js:2275-2281) solo
#   espera 5,5 s y vuelve a confirmar con el mismo token: sin
#   /verification/pending. Las peticiones con peek de la bandeja
#   (:2426 → :3410-3419 → chatboo_systray.js:67-73 y :262-268) solo cuentan y no
#   generan token: se informan, no son fallo;
# - Confirmar encadena /confirm y /execute (:2453-2463).
# Nunca se imprime ni se guarda un token: solo su SHA-256, en memoria, para
# comparar.
TOOL_TARJETA = 'seges_lab47'
CONTACTO_TARJETA = 'Seges P47 contacto de prueba'
COMENTARIO_TARJETA = 'Seges P47 reintento'
RUTA_VERIF = '/pns_ai_mcp/verification/'
ESPERA_TARJETA = 30       # segundos para que la tarjeta se pinte con token
ESPERA_FIN_TARJETA = 30   # segundos para el /execute tras el clic
ASIENTO_TARJETA = 3       # segundos tras el /execute para ver lo que llega después
MARGEN_TARJETA = 60       # segundos mínimos antes de que caduque la operación
REINTENTO_MIN, REINTENTO_MAX = 5.4, 7.0  # previsto: unos 5,5 s tras el rechazo
ERRORES_TARJETA = ('too_soon', 'bad_token', 'missing_token', 'busy', 'not_found',
                   'forbidden', 'missing_id', 'not_pending')
TARJETA_ESTADO_JS = r"""(() => {
  const c = document.getElementById('pns_verif_' + %s);
  if (!c) return {existe: false};
  const b = Array.from(c.querySelectorAll('button'))
    .find(x => /^Confirm/.test((x.textContent || '').trim()));
  return {existe: true, token: !!c.dataset.confirmToken, boton: !!b, deshabilitado: !!(b && b.disabled)};
})()"""
# Solo quita «disabled» al botón Confirmar y lanza el clic (decisión de Sergio,
# 17/11/2026): nada de funciones internas, del token ni de los tiempos.
TARJETA_CLIC_JS = r"""(() => {
  const c = document.getElementById('pns_verif_' + %s);
  if (!c) return {clic: false, motivo: 'sin-tarjeta'};
  const b = Array.from(c.querySelectorAll('button'))
    .find(x => /^Confirm/.test((x.textContent || '').trim()));
  if (!b) return {clic: false, motivo: 'sin-boton'};
  const antes = b.disabled, cuenta = /\(\d+s\)/.test(b.textContent || '');
  b.disabled = false;
  b.click();
  return {clic: true, deshabilitado: antes, cuenta: cuenta};
})()"""


def _huella(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest() if token else ''


def peticion_verificacion(url, post, t):
    """Lo que se guarda de una petición a /pns_ai_mcp/verification/*, o None.

    Ruta, hora (reloj de CDP), si es peek y la huella del token enviado.
    """
    ruta = urllib.parse.urlsplit(url or '').path
    if not ruta.startswith(RUTA_VERIF):
        return None
    try:
        params = (json.loads(post or '{}') or {}).get('params') or {}
    except (ValueError, AttributeError):
        params = {}
    if not isinstance(params, dict):
        params = {}
    token = params.get('confirm_token')
    return {'ruta': ruta[len(RUTA_VERIF):], 't': t, 'peek': bool(params.get('peek')),
            'huella': _huella(token if isinstance(token, str) else ''), 't_resp': None,
            'terminada': False, 'http': None, 'leida': False, 'success': None, 'error': '',
            'status': '', 'items': None, 'huella_vid': ''}


def resumen_respuesta(reg, texto, vid):
    """Anota en reg lo que interesa de la respuesta JSON-RPC (sin guardar el texto)."""
    reg['leida'] = True
    try:
        j = json.loads(texto)
    except ValueError:
        reg['error'] = 'respuesta ilegible'
        return
    if not isinstance(j, dict) or j.get('error'):
        reg['error'] = 'error RPC'
        return
    res = j.get('result') or {}
    if not isinstance(res, dict):
        return
    reg['success'] = res.get('success')
    err = res.get('error') or ''
    reg['error'] = err if err in ERRORES_TARJETA or not err else 'otro'
    reg['status'] = res.get('status') if res.get('status') in (
        'pending', 'confirmed', 'executed', 'cancelled', 'expired') else ''
    items = res.get('items')
    if isinstance(items, list):
        reg['items'] = len(items)
        for item in items:
            if isinstance(item, dict) and item.get('verification_id') == vid:
                tok = item.get('confirm_token')
                reg['huella_vid'] = _huella(tok if isinstance(tok, str) else '')


def leer_cuerpo(ch, reg, vid):
    if reg['ruta'] not in ('pending', 'confirm', 'execute') or not reg.get('terminada'):
        return
    try:
        r = ch.llamar('Network.getResponseBody', {'requestId': reg['id']}, ch.pagina)
    except ErrorCDP:
        reg['error'] = 'cuerpo no disponible'
        return
    texto = r.get('body') or ''
    if r.get('base64Encoded'):
        texto = base64.b64decode(texto).decode('utf-8', 'replace')
    resumen_respuesta(reg, texto, vid)


def motivo_tarjeta_no_lista(ops, uid):
    """Por qué no se puede lanzar el escenario (None si se puede). Solo lectura."""
    if len(ops) != 1:
        return ('hay %d operaciones %s (se espera 1): tarjeta_borrar.sh y tarjeta_plantar.sh'
                % (len(ops), TOOL_TARJETA))
    op = ops[0]
    if op['status'] != 'pending' or op['executed']:
        return 'la operación no está pendiente (estado %s)' % (op['status'] or '?')
    if op['danger'] != 'high':
        return 'la operación no es high'
    if op['uid'] != uid:
        return 'la operación no es del usuario de la sesión (uid %s)' % uid
    if not op['vigente']:
        return ('la operación ha caducado (15 min, pns_ai_mcp/constants.py:7): '
                'tarjeta_borrar.sh y otra vez tarjeta_plantar.sh')
    if op['restante'] < MARGEN_TARJETA:
        return 'la operación caduca en menos de %d s: bórrala y vuelve a plantarla' % MARGEN_TARJETA
    return None


def analizar_tarjeta(registro, n_clic):
    """(líneas, incidencias) de las peticiones a /verification/* antes y después del clic."""
    lineas, incid = [], []
    antes, despues = registro[:n_clic], registro[n_clic:]
    pinta = [r for r in antes if r['ruta'] == 'pending' and not r['peek'] and r['huella_vid']]
    huella = pinta[-1]['huella_vid'] if pinta else ''
    t_pinta = pinta[-1]['t_resp'] if pinta else None
    lineas.append('tarjeta pintada por /verification/pending (con token): %s' % _si(pinta))
    if not pinta:
        incid.append('la tarjeta no salió de /verification/pending')
    conf = [r for r in despues if r['ruta'] == 'confirm']
    pend = [r for r in despues if r['ruta'] == 'pending' and not r['peek']]
    peek = [r for r in despues if r['ruta'] == 'pending' and r['peek']]
    ejec = [r for r in despues if r['ruta'] == 'execute']
    otras = [r for r in despues if r['ruta'] not in ('confirm', 'pending', 'execute')]
    lineas.append('tras el clic: /confirm %d, /execute %d, /pending sin peek %d, /pending con peek '
                  '%d (bandeja, informativo), otras %d'
                  % (len(conf), len(ejec), len(pend), len(peek), len(otras)))
    if len(conf) != 2:
        incid.append('se esperaban 2 /confirm y hay %d' % len(conf))
    if pend:
        incid.append('%d /verification/pending sin peek tras el clic (se esperaba ninguna)' % len(pend))
    if otras:
        incid.append('%d peticiones a otras rutas de /verification' % len(otras))
    c1 = conf[0] if conf else None
    if c1:
        d0 = (c1['t'] - t_pinta) if (c1['t'] is not None and t_pinta is not None) else None
        lineas.append('primer /confirm: %s, a %s del pintado (forzado: antes de 5 s)' % (
            c1['error'] or ('éxito' if c1['success'] else 'sin error'),
            '%.2f s' % d0 if d0 is not None else '?'))
        if c1['error'] != 'too_soon':
            incid.append('el primer /confirm no fue too_soon')
        if d0 is None or d0 >= 5.0:
            incid.append('el clic no fue antes de 5 s desde el pintado')
    if len(conf) >= 2:
        c2 = conf[1]
        d = (c2['t'] - c1['t_resp']) if (c2['t'] is not None and c1['t_resp'] is not None) else None
        lineas.append('segundo /confirm: %s, %s después del rechazo (previsto unos 5,5 s)' % (
            c2['error'] or ('éxito' if c2['success'] is not False else 'fallo'),
            '%.2f s' % d if d is not None else '?'))
        if d is None or not REINTENTO_MIN <= d <= REINTENTO_MAX:
            incid.append('el segundo /confirm no llegó entre %.1f y %.1f s después del rechazo'
                         % (REINTENTO_MIN, REINTENTO_MAX))
        if c2['success'] is False or c2['error'] or not c2['leida']:
            incid.append('el segundo /confirm no confirmó')
        mismo = bool(huella) and c1['huella'] == huella and c2['huella'] == huella
        lineas.append('mismo token en los dos /confirm y en la tarjeta pintada: %s' % _si(mismo))
        if not mismo:
            incid.append('el token no es el mismo')
    if len(ejec) != 1:
        incid.append('se esperaba 1 /execute y hay %d' % len(ejec))
    else:
        e = ejec[0]
        lineas.append('/execute: %s' % (e['status'] or e['error'] or '?'))
        if e['status'] != 'executed' or e['success'] is False:
            incid.append('el /execute no dejó la operación ejecutada')
    return lineas, incid


def despues_tarjeta(ops, uid, n_contacto, comentado):
    """(líneas, incidencias) del SQL de solo lectura tras el clic."""
    lineas, incid = [], []
    if len(ops) != 1:
        return ['SQL después: %d operaciones' % len(ops)], ['SQL: no hay una sola operación']
    op = ops[0]
    lineas.append('SQL después: estado %s, ejecutada %s, confirmada por el usuario de la sesión %s; '
                  'contacto %d, comentario escrito %s' % (
                      op['status'], _si(op['executed']), _si(op['confirmado_por'] == uid),
                      n_contacto, _si(comentado)))
    if op['status'] != 'executed' or not op['executed']:
        incid.append('SQL: la operación no está ejecutada')
    if op['confirmado_por'] != uid:
        incid.append('SQL: no la confirmó el usuario de la sesión')
    if n_contacto != 1 or not comentado:
        incid.append('SQL: el comentario del contacto de prueba no está escrito')
    return lineas, incid


RE_LINEA_LOG = re.compile(
    r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ \d+ (\S+) (\S+) (\S+): (.*)')
RE_RETRY_MAS = re.compile(r'SERIALIZATION_FAILURE, retry [2-9]/\d')


def contar_tarjeta(texto, desde, bd):
    """Líneas del anexo de PNS-26 en la BD desde la marca UTC (solo recuentos)."""
    c = collections.Counter()
    for linea in texto.splitlines():
        m = RE_LINEA_LOG.search(linea)
        if not m or m.group(1) < desde or m.group(3) != bd:
            continue
        nivel, logger, msg = m.group(2), m.group(4), m.group(5)
        if logger == 'odoo.sql_db' and nivel == 'ERROR' and msg.startswith('bad query'):
            c['bad_query_aso' if 'ai_safe_operation' in msg else 'bad_query_otra'] += 1
        elif logger == 'odoo.service.model':
            if 'SERIALIZATION_FAILURE, retry 1/' in msg:
                c['retry1'] += 1
            elif RE_RETRY_MAS.search(msg):
                c['retry_mas'] += 1
            elif 'maximum number of tries reached' in msg:
                c['maximo'] += 1
    return c


def tarjeta_log_en_vivo(desde):
    salida = subprocess.run(
        ['odoo-dev', '14', 'log', 'all'], cwd=LAB,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=120,
    ).stdout
    return contar_tarjeta(salida.decode('utf-8', 'replace'), desde, BD)


class ConsultasTarjeta(Consultas):
    """Consultas del escenario tarjeta. Todas de solo lectura y sin contenidos."""

    def operaciones(self):
        filas = self.ejecutar(
            "SELECT id, verification_id, status, executed, coalesce(danger_level, ''), "
            "coalesce(user_id, 0), coalesce(expires_at > (now() AT TIME ZONE 'UTC'), false), "
            "coalesce(round(extract(epoch FROM expires_at - (now() AT TIME ZONE 'UTC')))::int, 0), "
            "coalesce(confirmed_by_uid, 0) "
            "FROM ai_safe_operation WHERE tool_name = '%s' ORDER BY id;" % TOOL_TARJETA)
        ops = []
        for f in filas:
            if len(f) != 9:
                raise ErrorSQL('fila de ai_safe_operation con %d campos' % len(f))
            ops.append({'id': int(f[0]), 'vid': f[1], 'status': f[2], 'executed': _t(f[3]),
                        'danger': f[4], 'uid': int(f[5]), 'vigente': _t(f[6]),
                        'restante': int(f[7]), 'confirmado_por': int(f[8])})
        return ops

    def comentario(self):
        f = self.una(
            "SELECT count(*), coalesce(bool_and(comment = '%s'), false) FROM res_partner "
            "WHERE name = '%s';" % (COMENTARIO_TARJETA, CONTACTO_TARJETA), 2)
        return int(f[0]), _t(f[1])


def escenario_tarjeta(ch, base, salida, uid, consultas, log_func=None):
    """Devuelve (incidencias, no confirmado, no concluyente)."""
    log_func = log_func or tarjeta_log_en_vivo
    print('\n== escenario tarjeta (D47): rechazo too_soon y reintento; clic FORZADO antes de 5 s')
    try:
        ops = consultas.operaciones()
    except ErrorSQL as e:
        print('  ABORTADO: SQL de la operación plantada: %s' % e)
        return [], True, False
    motivo = motivo_tarjeta_no_lista(ops, uid)
    if motivo:
        print('  NO se pulsa nada: %s' % motivo)
        return [], True, False
    op = ops[0]
    print('  SQL antes: operación %d pendiente, high, del uid %d, sin ejecutar; caduca en %d s'
          % (op['id'], op['uid'], op['restante']))
    desde = consultas.ahora()
    vid_js = json.dumps(op['vid'])
    incid = []
    registro, n_clic, fin_ok = [], 0, False
    ch.red = []
    try:
        ch.llamar('Network.enable', {}, ch.pagina)
        ch.nueva_medida('tarjeta')
        err = ch.ir(base + '/web')
        if err:
            print('  /web no carga: %s' % err)
            return [('tarjeta', 'carga de /web')], False, False
        abierto = ch.evaluar(CHAT_ABRIR_JS % {
            'espera': ESPERA_CHAT, 'relanzar': RELANZAR_MS, 'sin_bandeja': SIN_BANDEJA_MS},
            promesa=True, espera=ESPERA_CHAT + 30)
        if abierto != 'ok':
            print('  NO CONCLUYENTE: el chat no se abre (%s)' % abierto)
            return [], False, True
        if not ch.esperar(lambda: (ch.evaluar(TARJETA_ESTADO_JS % vid_js) or {}).get('token'),
                          ESPERA_TARJETA):
            print('  NO CONCLUYENTE: la tarjeta no se pintó con token en %d s' % ESPERA_TARJETA)
            return [], False, True
        n_clic = len(ch.red)
        clic = ch.evaluar(TARJETA_CLIC_JS % vid_js) or {}
        if not clic.get('clic'):
            print('  no se pudo pulsar: %s' % clic.get('motivo', '?'))
            return [('tarjeta', 'sin botón Confirmar')], False, False
        print('  clic FORZADO: botón deshabilitado antes del clic %s; con cuenta atrás %s' % (
            _si(clic.get('deshabilitado')), _si(clic.get('cuenta'))))
        fin_ok = ch.esperar(lambda: any(r['ruta'] == 'execute' and r['terminada'] for r in ch.red),
                            ESPERA_FIN_TARJETA)
        ch.bombear(ASIENTO_TARJETA)
        png = os.path.join(salida, 'tarjeta.png')
        ch.captura(png)
        for r in ch.red:
            leer_cuerpo(ch, r, op['vid'])
        incid += resumir('tarjeta (navegador)', None, [], ch.medida, png, con_marcos=False)
    finally:
        registro, ch.red = ch.red or [], None
        try:
            ch.llamar('Network.disable', {}, ch.pagina)
        except ErrorCDP:
            pass
    print('\n== tarjeta (peticiones)')
    lineas, inc = analizar_tarjeta(registro, n_clic)
    if not fin_ok:
        inc.append('sin /execute terminado en %d s' % ESPERA_FIN_TARJETA)
    for linea in lineas:
        print('  ' + linea)
    incid += inc
    try:
        lineas, inc = despues_tarjeta(consultas.operaciones(), uid, *consultas.comentario())
    except ErrorSQL as e:
        print('  ABORTADO: SQL después: %s' % e)
        return [('tarjeta', i) for i in incid], True, False
    for linea in lineas:
        print('  ' + linea)
    incid += inc
    cuenta = log_func(desde)
    print('  log (%s desde %s UTC): «bad query» sobre ai_safe_operation %d, «bad query» sin '
          'ai_safe_operation en la línea %d, «retry 1/5» %d (anexo de PNS-26, previsto 1 y 1 por '
          'cada /execute correcto: no son fallo); «retry 2/5» o más %d, «maximum number of tries '
          'reached» %d (fallo si alguno)' % (
              BD, desde, cuenta['bad_query_aso'], cuenta['bad_query_otra'], cuenta['retry1'],
              cuenta['retry_mas'], cuenta['maximo']))
    if cuenta['retry_mas'] or cuenta['maximo']:
        incid.append('log: reintentos de serialización más allá del 1/5')
    for i in incid:
        print('  INCIDENCIA: %s' % i)
    print('  escenario tarjeta: %s' % ('como se espera' if not incid else '%d incidencias' % len(incid)))
    return [('tarjeta', i) for i in incid], False, False


def sqlprueba_tarjeta(consultas=None):
    """Las consultas del escenario tarjeta contra la BD real, en solo lectura."""
    q = consultas or ConsultasTarjeta()
    fallos = 0
    for nombre, f in (
            ('hora del servidor', lambda: 'leída' if q.ahora() else ''),
            ('operaciones %s' % TOOL_TARJETA, lambda: '%d filas' % len(q.operaciones())),
            ('contacto de prueba', lambda: '%d, comentario escrito %s' % (
                q.comentario()[0], _si(q.comentario()[1])))):
        try:
            print('  %-45s OK (%s)' % (nombre, f()))
        except ErrorSQL as e:
            fallos += 1
            print('  %-45s FALLA: %s' % (nombre, e))
    print('Consultas del escenario tarjeta: %s' % ('todas OK' if not fallos else '%d FALLA' % fallos))
    return OK if not fallos else NO_CONFIRMADO


def navegar(args, base=BASE, c_func=c_en_vivo, login=None, clave=None, espera_servidor=120,
            consultas=None, pausa=pausa_terminal, repetir=repetir_terminal, motor=motor_en_vivo,
            continuar=None):
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
        ch = Chrome(perfil, args.salida, visible=getattr(args, 'visible', False))
    except OSError as e:
        print('ABORTADO: Chrome no arranca (%s)' % e.__class__.__name__)
        shutil.rmtree(perfil, ignore_errors=True)
        shutil.rmtree(descargas, ignore_errors=True)
        return FALLA_CHROME
    incidencias = []
    no_concluyente = False
    no_confirmado = False
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
        if getattr(args, 'escenario', None) == 'p34':
            incid, no_confirmado, nc = escenario_p34(
                ch, base, args.salida, info.get('uid'), consultas or Consultas(), pausa, repetir,
                getattr(args, 'espera_turno', None) or ESPERA_TURNO, motor=motor, continuar=continuar)
            incidencias += incid
            no_concluyente = no_concluyente or nc
            print('\nalert() en total: %d; otros diálogos aceptados: %d' % (ch.alertas, ch.otros_dialogos))
        if getattr(args, 'escenario', None) == 'tarjeta':
            incid, nconf, nc = escenario_tarjeta(
                ch, base, args.salida, info.get('uid'), consultas or ConsultasTarjeta())
            incidencias += incid
            no_confirmado = no_confirmado or nconf
            no_concluyente = no_concluyente or nc
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
        print('NO CONCLUYENTE: el formateador del cliente no se encontró o algún paso del '
              'escenario no prueba nada')
    if no_confirmado:
        print('NO CONFIRMADO: una condición o un paso manual del escenario no se confirmó por SQL')
    print('Peticiones a /web/database bloqueadas en total: %d' % ch.bloqueadas)
    if incidencias:
        return INCIDENCIAS
    if no_confirmado:
        return NO_CONFIRMADO
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
    # Un cliente que deja etiquetas a la vista: pintado distinto de lo previsto.
    'distinto': FORMATEADOR_SIMULADO + '''
window.odoo = {__DEBUG__: {services: {'pns_ai_chatboo.formatters':
  {formatContent: function (s) { return segesEsc(s) + '&lt;/em&gt;'; }}}}};
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


# Chat simulado para --escenario p34: los mismos puntos de apoyo que usa el
# script en el cliente real (bus, componente, textarea, burbujas). Pinta con
# FORMATEADOR_SIMULADO; no es el JS del fabricante.
CHAT_SIMULADO = FORMATEADOR_SIMULADO + r'''
function segesPost(ruta, datos) {
  return fetch(ruta, {method: 'POST', headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify(datos || {})}).then(function (r) { return r.json(); });
}
function segesAbrir() {
  if (window.__chatboo_component) { return; }
  var ta = document.createElement('textarea');
  ta.className = 'o_chatboo_prompt';
  var caja = document.createElement('div');
  document.body.appendChild(caja);
  document.body.appendChild(ta);
  function pintar(msgs) {
    caja.innerHTML = '';
    msgs.forEach(function (m) {
      var d = document.createElement('div'), c = document.createElement('div');
      d.className = 'o_chatboo_message';
      if (m.role === 'assistant') { d.setAttribute('data-ai-generated', 'true'); }
      c.className = 'o_chatboo_content';
      c.innerHTML = m.role === 'assistant' ? segesFormatea(m.content) : segesEsc(m.content);
      d.appendChild(c);
      caja.appendChild(d);
    });
  }
  window.__chatboo_component = {
    state: {thinking: false, currentSessionId: null, currentInput: ''},
    _createNewSession: async function () {
      var r = await segesPost('/sim/nueva');
      this.state.currentSessionId = r.id;
      pintar([]);
    },
    _selectSession: async function (id) {
      this.state.thinking = true;
      var r = await segesPost('/sim/sesion', {id: id});
      if (r.msgs) { this.state.currentSessionId = id; pintar(r.msgs); }
      this.state.thinking = false;
    },
    _sendMessage: async function () {
      var texto = ta.value;
      ta.value = '';
      this.state.thinking = true;
      var r = await segesPost('/sim/turno', {sid: this.state.currentSessionId, texto: texto});
      pintar(r.msgs);
      if (!r.colgado) { this.state.thinking = false; }
    },
  };
}
// Como en Odoo: web.core existe enseguida, pero la bandeja solo escucha desde
// su start() (con .o_chatboo_systray_item); un evento anterior se pierde.
var segesEscucha = false;
setTimeout(function () {
  if (window.SEGES_SIN_CHAT) { return; }
  var item = document.createElement('div');
  item.className = 'o_chatboo_systray_item';
  item.style.display = 'none';
  document.body.appendChild(item);
  segesEscucha = true;
}, 1500);
window.odoo = {__DEBUG__: {services: {'web.core': {bus: {trigger: function (ev) {
  if (ev === 'chatboo_overlay_show' && segesEscucha) { setTimeout(segesAbrir, 300); } }}}}}};
'''
HOSTIL = "Seges P34 </script><script>alert('P34')</script>"
DISENO_PLANTADO = ('<html><head><title>t</title></head><body><section id="pns-page-rows"><table><tr><td>%s'
                   '</td></tr></table></section><script>const DATA = [{"name": "%s"}];</script>'
                   '</body></html>' % (html.escape(HOSTIL), HOSTIL))
DISENO_ESCAPADO = ('<html><head><title>t</title></head><body><h1>Contactos</h1><script>const DATA = '
                   '[{"name": "Seges P34 \\u003c/script\\u003e\\u003cscript\\u003ealert(\'P34\')'
                   '\\u003c/script\\u003e"}];</script></body></html>')
ID_PLANTADA = 50


def estado_simulado(variante='bien'):
    """Lo que el chat simulado y las consultas simuladas comparten."""
    return {
        'variante': variante, 'design': True, 'contactos': 0,
        'reloj': 0, 'log': [], 'siguiente': 100, 'errores': 0, 'motor': [], 'sin_chat': False,
        'sesiones': {ID_PLANTADA: {'uid': 99, 'rev': 1, 'design': DISENO_PLANTADO, 'msgs': [],
                                   'nombre': NOMBRE_PLANTADA, 'abierta': True}},
    }


def turno_simulado(e, sid, texto):
    """El servidor simulado contesta según el mensaje y la variante."""
    v, s = e['variante'], e['sesiones'][sid]
    nota = NOTAS_P34['en']
    acc = 'Hecho.'

    def con_aviso(motivo):
        e['reloj'] += 1
        e['log'].append((e['reloj'], 'No page was built: ' + motivo))
        if v == 'con_marcas':
            return '%s\n\n_%s_' % (acc, nota)
        if v == 'sin_aviso':
            return acc
        return componer_p34(acc, nota)

    msg = {'role': 'assistant'}
    if v in ('chat_cae', 'proveedor_cae', 'proveedor_cae_una_vez', 'motor_con_rechazo', 'proveedor_caido'):
        e['reloj'] += 1
    if texto == MENSAJES_P34['T1'] and v == 'chat_cae':
        e['sin_chat'] = True  # la página recargada ya no trae el chat
    if texto == MENSAJES_P34['T1'] and v == 'motor_con_rechazo':
        e['motor'].append((e['reloj'], 'ERROR'))
    if v == 'proveedor_caido':
        # Como el tercer intento del 17/11: todos los turnos caen (timeout o 429).
        e['motor'] += [(e['reloj'], 'ERROR'), (e['reloj'], 'WARNING')]
        msg['content'] = 'Lo siento, no he podido completar la petición.'
    elif texto == MENSAJES_P34['T1'] and v in ('proveedor_cae', 'proveedor_cae_una_vez') \
            and not e['errores']:
        # Como el 17/11: ERROR del motor, WARNING de failover y respuesta normal, sin is_error.
        e['errores'] += v == 'proveedor_cae_una_vez'
        e['motor'] += [(e['reloj'], 'ERROR'), (e['reloj'], 'WARNING')]
        msg['content'] = 'Lo siento, no he podido completar la petición.'
    elif texto == MENSAJES_P34['T1'] and v in ('error', 'error_una_vez') and not e['errores']:
        e['errores'] += v == 'error_una_vez'
        msg.update(content='MCP engine error: 503', is_error=True)
    elif v == 'sin_page_tab' and texto in (MENSAJES_P34['T1'], MENSAJES_P34['T1b'],
                                           MENSAJES_P34['V2'], MENSAJES_P34['5b′']):
        msg['content'] = '<table><tr><td>1</td></tr></table>'  # tabla en el chat, sin página
    elif texto in (MENSAJES_P34['T1'], MENSAJES_P34['T1b'], MENSAJES_P34['V2']):
        if texto == MENSAJES_P34['T1b']:
            acc = TABLA_P34 + '\n\nHecho.'
        if e['design'] and not (v == 'v2_sin_pagina' and texto == MENSAJES_P34['V2']):
            s['rev'] += 1
            s['design'] = DISENO_LIMPIO
            msg['content'] = acc
        elif v == 'v2_sin_pagina' and e['design']:
            msg['content'] = acc
        else:
            msg['content'] = con_aviso(MOTIVO_SIN_DESIGN + ': simulado')
    elif texto == MENSAJES_P34['5b′']:
        s['rev'] += 1
        s['design'] = DISENO_PLANTADO if v == 'crudo' else DISENO_ESCAPADO
        msg['content'] = acc
    elif texto == MENSAJES_P34['6c']:
        s['rev'] += 1
        msg['content'] = acc
    elif texto == MENSAJES_P34['6d′']:
        if v == '6d_reescribe':
            s['rev'] += 1
            s['design'] = DISENO_LIMPIO
            msg['content'] = acc
        elif v == '6d_nada':
            msg['content'] = acc
        elif v == '6d_timeout' and not e['errores']:
            e['errores'] += 1
            msg['content'] = con_aviso('timed out: simulado')
        else:
            msg['content'] = con_aviso(MOTIVO_MARCADO)
    else:
        msg['content'] = 'No entiendo.'
    msg['original_content'] = acc if v == 'original_distinto' else msg['content']
    s['msgs'] += [{'role': 'user', 'content': texto}, msg]
    return {'msgs': s['msgs'], 'colgado': v == 'colgado'}


def motor_simulado(e):
    def contar(desde):
        filas = [n for t, n in e['motor'] if t >= int(desde)]
        return sum(1 for n in filas if n != 'WARNING'), filas.count('WARNING')
    return contar


class ConsultasSimuladas:
    """Las mismas respuestas que Consultas, leídas del estado simulado."""

    def __init__(self, e):
        self.e = e

    def columnas_rel(self):
        return ('ai_provider_id', 'ai_provider_role_id')

    def design(self):
        return True, self.e['design']

    def ahora(self):
        self.e['reloj'] += 1
        return str(self.e['reloj'])

    def no_page(self, desde, motivo=''):
        return sum(1 for t, texto in self.e['log']
                   if t >= int(desde) and texto.startswith('No page was built: ' + motivo))

    def sesion(self, sid):
        s = self.e['sesiones'].get(sid)
        if not s:
            return None
        d = s['design']
        return {'rev': s['rev'], 'lienzo': bool(d), 'cierra_script': '</script><script>alert' in d,
                'escapado': '\\u003c/script\\u003e\\u003cscript\\u003ealert' in d,
                'escapado_tabla': False, 'uid': s['uid']}

    def mensaje(self, sid):
        s = self.e['sesiones'].get(sid)
        if not s or not s['msgs']:
            return None
        m = s['msgs'][-1]
        c = m.get('content') or ''
        return {'asistente': m.get('role') == 'assistant',
                'aviso': any(n in c for n in NOTAS_P34.values()),
                'iguales': c == (m.get('original_content') or ''), 'error': bool(m.get('is_error')),
                'al_final': any(c.rstrip().endswith(n) for n in NOTAS_P34.values()),
                'html': c.lstrip().startswith('<')}

    def motivos(self, desde):
        return [('valor en crudo' if MOTIVO_MARCADO in texto else
                 'sin proveedor Design' if MOTIVO_SIN_DESIGN in texto else 'timeout')
                for t, texto in self.e['log'] if t >= int(desde)]

    def page_tab(self, desde):
        return 1, self.e['variante'] != 'sin_page_tab'

    def contacto(self):
        return self.e['contactos']

    def plantada(self):
        return [(i, s['rev'], s['uid'], s['abierta']) for i, s in sorted(self.e['sesiones'].items())
                if s.get('nombre') == NOMBRE_PLANTADA]


def servidor_simulado(error_js_login=False, bd_sesion=BD, cliente=None, js_dir=None, estado=None):
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
                elif estado is not None:
                    if estado.get('sin_chat'):
                        extra_js += b'<script>window.SEGES_SIN_CHAT = true;</script>'
                    extra_js += ('<script>%s</script>' % CHAT_SIMULADO).encode()
                return self._resp(200, b'<!DOCTYPE html><title>web</title><p>web</p>' + extra_js)
            if js_dir and u.path.startswith('/seges_js/') and u.path[10:] in JS_REALES:
                with open(os.path.join(js_dir, u.path[10:]), 'rb') as f:
                    return self._resp(200, f.read(), 'text/javascript; charset=utf-8')
            hdr = [('Content-Security-Policy', CSP_FAB), ('X-Content-Type-Options', 'nosniff')]
            lienzo = re.match(r'^/chatboo/canvas/(\d+)$', u.path)
            if estado is not None and lienzo and int(lienzo.group(1)) in estado['sesiones']:
                return self._resp(200, self._carcasa(
                    estado['sesiones'][int(lienzo.group(1))]['design']), extra=hdr)
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
            if estado is not None and u.path.startswith('/sim/') and self._sesion():
                d = json.loads(cuerpo.decode() or '{}')
                if u.path == '/sim/nueva':
                    estado['siguiente'] += 1
                    estado['sesiones'][estado['siguiente']] = {
                        'uid': 99, 'rev': 0, 'design': '', 'msgs': [], 'abierta': False}
                    r = {'id': estado['siguiente']}
                elif u.path == '/sim/sesion':
                    r = {'msgs': estado['sesiones'].get(d.get('id'), {}).get('msgs')}
                else:
                    time.sleep(0.3)
                    r = turno_simulado(estado, d.get('sid'), d.get('texto') or '')
                return self._resp(200, json.dumps(r).encode(), 'application/json')
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
    ver('composición como el servidor (D25, línea llana)',
        componer_p34('<p>x</p>', 'N.') == '<p>x</p>\n\nN.'
        and componer_p34('x', 'N.') == 'x\n\nN.' and componer_p34('', 'N.') == 'N.'
        and componer_p34('  ', 'N.') == 'N.')
    ver('clases del pintado: ausente, etiquetas, guiones, cursiva y línea llana',
        [clase_pintado(dict(presente=p, etiquetas=e, guiones=g, cursiva=c)) for p, e, g, c in (
            (0, 0, 0, 0), (1, 1, 0, 0), (1, 0, 1, 0), (1, 0, 0, 1), (1, 0, 0, 0))]
        == ['ausente', 'etiquetas literales', 'guiones literales', 'cursiva', 'línea llana'])
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

    print('--- Escenario p34 (--escenario p34, parche 34, L2)')
    global PSQL
    ver('rutas --escenario p34 --visible → 0', orden('rutas', '--escenario', 'p34', '--visible') == OK)
    ver('rutas --escenario desconocido → 12', orden('rutas', '--escenario', 'otro') == ARGUMENTOS)
    ver('rutas --espera-turno 0 → 12',
        orden('rutas', '--escenario', 'p34', '--espera-turno', '0') == ARGUMENTOS)
    ver('seis mensajes, uno por paso', sorted(MENSAJES_P34) == sorted(('T1', 'T1b', 'V2', '5b′', '6c', '6d′')))
    # psql simulado: comprueba la forma de la orden (solo lectura) y devuelve filas.
    falso = os.path.join(args.salida, 'psql_falso.py')
    with open(falso, 'w', encoding='utf-8') as f:
        f.write('import os, sys\n'
                'c = sys.stdin.read()\n'
                'if "read_only=on" not in os.environ.get("PGOPTIONS", ""):\n'
                '    sys.exit(3)\n'
                'if "falla" in c:\n'
                '    sys.stderr.write("ERROR:  column \\"x\\" does not exist\\n"); sys.exit(1)\n'
                'if "information_schema" in c:\n'
                '    print("ai_provider_id"); print("ai_provider_role_id")\n'
                'elif "ai_provider_role_rel" in c:\n'
                '    ok = "x.ai_provider_role_id" in c and "x.ai_provider_id = 2" in c\n'
                '    print("1|1" if ok else "0|0")\n'
                'elif "to_char" in c:\n'
                '    print("2026-11-16 18:00:00")\n'
                'elif "domain_index" in c:\n'
                '    print("3|t")\n'
                'elif "ai_log" in c and "CASE" in c:\n'
                '    print("valor en crudo")\n'
                'elif "ai_log" in c:\n'
                '    print("2")\n'
                'elif "jsonb" in c:\n'
                '    print("t|t|t|f|t|f")\n'
                'elif "FROM chatboo_session WHERE id" in c:\n'
                '    print("3|t|f|t|f|12")\n'
                'elif "res_partner" in c:\n'
                '    print("1")\n'
                'else:\n'
                '    print("50|1|12|t")\n')
    psql_real = PSQL
    try:
        PSQL = ['env', 'PGOPTIONS=-c default_transaction_read_only=on', sys.executable, '-I', falso]
        q = Consultas()
        ver('psql simulado: columnas, Design, hora, ai_log, sesión, mensaje, contacto y plantada',
            q.columnas_rel() == ('ai_provider_id', 'ai_provider_role_id') and q.design() == (True, True)
            and q.ahora() == '2026-11-16 18:00:00' and q.no_page('2026-11-16 18:00:00', MOTIVO_MARCADO) == 2
            and q.sesion(7) == {'rev': 3, 'lienzo': True, 'cierra_script': False, 'escapado': True,
                                'escapado_tabla': False, 'uid': 12}
            and q.mensaje(7) == {'asistente': True, 'aviso': True, 'iguales': True, 'error': False,
                                 'al_final': True, 'html': False}
            and q.contacto() == 1 and q.plantada() == [(50, 1, 12, True)]
            and q.motivos('2026-11-16 18:00:00') == ['valor en crudo']
            and q.page_tab('2026-11-16 18:00:00') == (3, True))
        try:
            q.no_page('ayer')
            ver('marca de tiempo no válida → ErrorSQL', False)
        except ErrorSQL:
            ver('marca de tiempo no válida → ErrorSQL', True)
        try:
            sql('falla')
            ver('error de psql → ErrorSQL sin datos', False)
        except ErrorSQL as e:
            ver('error de psql → ErrorSQL sin datos', 'psql terminó con 1' in str(e))
        real = sys.stdout
        sys.stdout = capt = io.StringIO()
        try:
            rc_sql = sqlprueba()
        finally:
            sys.stdout = real
        ver('sqlprueba con el psql simulado → 0', rc_sql == OK and 'todas OK' in capt.getvalue())
        PSQL = ['env', sys.executable, '-I', falso]
        try:
            sql('SELECT 1;')
            ver('psql sin solo lectura → ErrorSQL', False)
        except ErrorSQL:
            ver('psql sin solo lectura → ErrorSQL', True)
        PSQL = [os.path.join(args.salida, 'no-existe-docker')]
        sys.stdout = io.StringIO()
        try:
            rc_sql = sqlprueba()
        finally:
            sys.stdout = real
        ver('sqlprueba sin docker → 9', rc_sql == NO_CONFIRMADO)
    finally:
        PSQL = psql_real

    global ASIENTO, SONDEO, ESPERA_PINTADO
    tiempos_reales = (ASIENTO, SONDEO, ESPERA_PINTADO)
    ASIENTO, SONDEO, ESPERA_PINTADO = 0.6, 0.2, 1  # el chat simulado contesta en 0,3 s
    global ESPERA_CHAT, RELANZAR_MS
    chat_real = (ESPERA_CHAT, RELANZAR_MS)
    ESPERA_CHAT, RELANZAR_MS = 8, 1000

    muestra = '\n'.join((
        'web-1  | 2026-11-17 09:33:20,001 1 INFO %s odoo.addons.pns_ai_mcp.utils.agent_engine: x' % BD,
        'web-1  | 2026-11-17 09:33:26,032 1 ERROR %s odoo.addons.pns_ai_mcp.utils.engine_tool_loop: x' % BD,
        'web-1  | 2026-11-17 09:33:26,040 1 WARNING %s odoo.addons.pns_ai_mcp.utils.agent_engine: x' % BD,
        'web-1  | 2026-11-17 09:33:27,000 1 ERROR otra_14 odoo.addons.pns_ai_mcp.utils.engine_tool_loop: x',
        'web-1  | 2026-11-17 09:33:28,000 1 ERROR %s odoo.http: x' % BD,
        'web-1  | 2026-11-17 09:20:00,000 1 ERROR %s odoo.addons.pns_ai_mcp.utils.engine_tool_loop: x' % BD))
    ver('log del motor: cuenta ERROR y WARNING de pns_ai_mcp en la BD desde la marca',
        contar_motor(muestra, '2026-11-17 09:30:00') == (1, 1)
        and contar_motor(muestra, '2026-11-17 09:40:00') == (0, 0))

    def escenario(variante, espera_turno=20, pausa_ok=True, repetir_si=False, continuar_si=True):
        e = estado_simulado(variante)
        srv_e = servidor_simulado(estado=e)
        pausas, repeticiones, continuaciones = [], [], []

        def pausa(_ch, texto):
            pausas.append(texto)
            if pausa_ok and 'quita el rol' in texto:
                e['design'] = False
                e['contactos'] = 0 if variante == 'sin_contacto' else 1
            elif pausa_ok and 'vuelve a marcar' in texto:
                e['design'] = True
            elif pausa_ok and 'archiva el contacto' in texto:
                e['contactos'] = 0
            return True

        def repetir(_ch, texto):
            repeticiones.append(texto)
            return repetir_si

        def continuar(_ch, texto):
            continuaciones.append(texto)
            return continuar_si

        try:
            codigo, texto = _navegar_capturado(
                argparse.Namespace(salida=sub_carpeta('p34_' + variante), rutas=[], descarga=[],
                                   escenario='p34', espera_turno=espera_turno),
                'http://127.0.0.1:%d' % srv_e.server_address[1], c_func=c_bueno, login='prueba',
                clave='clave-prueba', consultas=ConsultasSimuladas(e), pausa=pausa, repetir=repetir,
                motor=motor_simulado(e), continuar=continuar)
        finally:
            srv_e.shutdown()
        e['continuaciones'] = continuaciones
        return codigo, texto, e, pausas, repeticiones

    def lineas(texto, paso):
        return [x for x in texto.splitlines() if x.startswith('  %-7s ' % paso)]

    codigo, texto, e, pausas, _rep = escenario('bien')
    print(texto[texto.find('\n== p34 paso 0'):])
    ver('todo como se prevé → código 0, seis pasos OK y tres pausas',
        codigo == OK and texto.count(' OK ') >= 6 and len(pausas) == 3
        and all(' OK ' in (lineas(texto, p) or [''])[0] for p in MENSAJES_P34))
    ver('al acabar: «Design» marcado, contacto archivado y segunda ventana cerrada',
        e['design'] is True and e['contactos'] == 0 and 'ATENCIÓN' not in texto
        and 'contactos de D23 activos: 0 (intento 1' in texto)
    ver('alert(): 0 en 5b′ y 6c; el del lienzo plantado, informativo',
        texto.count('alert(): 0;') == 2 and 'control (informativo): alert() del lienzo plantado: 1' in texto)
    ver('cada turno dice si se activó page_tab y el motivo del rechazo',
        texto.count('paquete page_tab activado en el turno: sí') == 6
        and '(motivo: sin proveedor Design)' in texto and '(motivo: valor en crudo)' in texto)
    ver('mensajes en inglés (en_US): todos piden una página («page»)',
        all('page' in m for k, m in MENSAJES_P34.items() if k != '6c'))
    ver('capturas de cada burbuja, en vivo y tras recargar',
        all(n in os.listdir(os.path.join(args.salida, 'p34_bien'))
            for n in ('p34_T1_vivo.png', 'p34_T1_recarga.png', 'p34_6d_recarga.png', 'p34_5b_lienzo.png')))
    ver('la salida no lleva el nombre hostil ni el texto de los mensajes',
        'Seges P34 <' not in texto and MENSAJES_P34['6c'] not in texto and 'Hecho.' not in texto)
    for variante, nombre, esperado, textos in (
            ('con_marcas', 'aviso con marcas → incidencia en T1, código 1', INCIDENCIAS,
             ('guiones literales', 'p34 → T1')),
            ('sin_aviso', 'rechazo sin aviso → incidencia, código 1', INCIDENCIAS, ('p34 → T1',)),
            ('original_distinto', 'original_content distinto de content → código 1', INCIDENCIAS,
             ('original_content = content no',)),
            ('crudo', 'valor hostil en crudo en 5b′ (alert) → código 1', INCIDENCIAS, ('p34 → 5b′',)),
            ('error', 'error del proveedor en T1, sin repetir → código 8', NO_CONCLUYENTE,
             ('de error sí',)),
            ('v2_sin_pagina', 'V2 sin página → código 8', NO_CONCLUYENTE, ('no se creó la página',)),
            ('6d_reescribe', '6d′: la página se sustituye → código 8', NO_CONCLUYENTE,
             ('la página se sustituyó',)),
            ('6d_nada', '6d′: dos intentos sin rechazo → código 8', NO_CONCLUYENTE,
             ('6d′, intento 2 de 2', 'no hubo rechazo')),
            ('sin_contacto', 'no se crea el contacto de D23 → código 9, sin turnos', NO_CONFIRMADO,
             ('falta el contacto de D23',))):
        codigo, texto, e, pausas, _rep = escenario(variante)
        ver(nombre, codigo == esperado and all(t in texto for t in textos)
            and e['design'] is True and e['contactos'] == 0
            and (variante != 'sin_contacto' or '== p34 T1' not in texto))
    codigo, texto, e, pausas, reps = escenario('error_una_vez', repetir_si=True)
    ver('error del proveedor una vez y se repite el paso → código 0',
        codigo == OK and len(reps) == 1 and ' OK ' in (lineas(texto, 'T1') or [''])[0])
    codigo, texto, e, pausas, _rep = escenario('colgado', espera_turno=4)
    ver('turno que no termina → código 8, «Design» marcado y contacto archivado',
        codigo == NO_CONCLUYENTE and 'fin del turno: no' in texto and e['design'] is True
        and e['contactos'] == 0)
    codigo, texto, e, pausas, _rep = escenario('bien', pausa_ok=False)
    ver('pausa sin confirmar por SQL (3 intentos) → código 9 y aviso de «Design»',
        codigo == NO_CONFIRMADO and len(pausas) >= INTENTOS_PAUSA and 'paso 1' in texto
        and '== p34 T1' not in texto)
    codigo, texto, e, pausas, reps = escenario('proveedor_cae')
    ver('fallo del proveedor sin is_error (como el 17/11), sin repetir → T1 no concluyente, código 8',
        codigo == NO_CONCLUYENTE and len(reps) == 1 and 'falló el proveedor (1 líneas ERROR' in reps[0]
        and 'NO CONCLUYENTE  falló el proveedor' in (lineas(texto, 'T1') or [''])[0]
        and 'log del motor (pns_ai_mcp) desde el inicio del turno: 1 ERROR, 1 WARNING' in texto)
    codigo, texto, e, pausas, reps = escenario('proveedor_cae_una_vez', repetir_si=True)
    ver('fallo del proveedor sin is_error una vez y se repite → código 0',
        codigo == OK and len(reps) == 1 and ' OK ' in (lineas(texto, 'T1') or [''])[0])
    codigo, texto, e, pausas, reps = escenario('motor_con_rechazo')
    ver('ERROR del motor pero con rechazo → T1 se juzga igual (OK), sin preguntar',
        codigo == OK and not reps and ' OK ' in (lineas(texto, 'T1') or [''])[0])
    codigo, texto, e, pausas, reps = escenario('sin_page_tab')
    ver('sin page_tab (como el 17/11) → T1, T1b, V2 y 5b′ no concluyentes con la causa, código 8',
        codigo == NO_CONCLUYENTE
        and all('el paquete page_tab no se activó' in (lineas(texto, p) or [''])[0]
                for p in ('T1', 'T1b', 'V2', '5b′')))
    codigo, texto, e, pausas, reps = escenario('6d_timeout', repetir_si=True)
    ver('6d′: rechazo por timeout → aviso juzgado, se ofrece repetir y el 2.º intento da OK',
        codigo == OK and len(reps) == 1 and 'rechazo por otro motivo (timeout)' in reps[0]
        and 'rechazo por valor en crudo' in (lineas(texto, '6d′') or [''])[0])
    codigo, texto, e, pausas, reps = escenario('6d_timeout')
    ver('6d′: rechazo por timeout sin repetir → no concluyente con el motivo, código 8',
        codigo == NO_CONCLUYENTE and len(reps) == 1
        and 'rechazo por otro motivo (timeout): aviso en línea llana correcto'
        in (lineas(texto, '6d′') or [''])[0])
    codigo, texto, e, pausas, reps = escenario('proveedor_caido', continuar_si=False)
    ver('proveedor caído en T1 y T1b y «no» a continuar → resto no ejecutado, limpieza hecha, código 8',
        codigo == NO_CONCLUYENTE and len(e['continuaciones']) == 1
        and 'ha fallado en 2 pasos seguidos' in e['continuaciones'][0]
        and all('NO EJECUTADO' in (lineas(texto, p) or [''])[0] for p in ('V2', '5b′', '6c', '6d′'))
        and 'mensaje V2 enviado' not in texto and e['design'] is True and e['contactos'] == 0)
    codigo, texto, e, pausas, reps = escenario('proveedor_caido', continuar_si=True)
    ver('proveedor caído y «sí» a continuar → se ejecuta todo y se vuelve a preguntar tras otros dos',
        codigo == NO_CONCLUYENTE and len(e['continuaciones']) == 2 and 'NO EJECUTADO' not in texto
        and 'mensaje 6d′ enviado' in texto)
    codigo, texto, e, pausas, reps = escenario('proveedor_cae')
    ver('un solo paso con el proveedor caído → no se pregunta si se sigue',
        not e['continuaciones'])
    codigo, texto, e, pausas, reps = escenario('chat_cae')
    t1 = texto[texto.find('== p34 T1'):texto.find('== p34 limpieza')]
    ver('el chat no se abre tras recargar → SQL y log del turno antes de abortar, código 9',
        codigo == NO_CONFIRMADO and 'SQL sesión:' in t1 and 'SQL último mensaje:' in t1
        and 'SQL ai_log' in t1 and 'log del motor' in t1 and 'ABORTADO' in t1
        and 'sin-bandeja' in t1 and e['design'] is True and e['contactos'] == 0)
    ESPERA_CHAT, RELANZAR_MS = chat_real
    ASIENTO, SONDEO, ESPERA_PINTADO = tiempos_reales

    autoprueba_rama(ver)
    print('\nAutoprueba: %s' % ('todo PASA' if not fallos else '%d FALLA' % fallos))
    return OK if not fallos else INCIDENCIAS


def autoprueba_rama(ver):
    """--lab/--bd (D44) y el análisis del escenario tarjeta (D47), sin Chrome ni Odoo."""
    print('--- --lab y --bd (D44)')
    psql_antes = list(PSQL)
    ver('--lab y --bd válidos cambian BD, LAB, PERMITIDAS y la BD de psql',
        configurar('lab_pns_ai_879', 'lab_p2a_879_14') is None and BD == 'lab_p2a_879_14'
        and LAB.endswith('/GitHub/lab_pns_ai_879') and PERMITIDAS == {'?', 'lab_p2a_879_14'}
        and PSQL[PSQL.index('-d') + 1] == 'lab_p2a_879_14' and len(PSQL) == len(psql_antes))
    real = sys.stdout
    sys.stdout = io.StringIO()
    try:
        c_otra = resultado_c(io.StringIO(LOG_BUENO.replace('lab_pns_ai_3973_14', 'lab_p2a_879_14')))
        c_3973 = resultado_c(io.StringIO(LOG_BUENO))
    finally:
        sys.stdout = real
    ver('C con --bd lab_p2a_879_14: su log da 0 y el de lab_pns_ai_3973_14 da otra BD (3)',
        c_otra == OK and c_3973 == OTRA_BD)
    ver('--lab y --bd no válidos se rechazan',
        configurar('../x', None) and configurar('a/b', None) and configurar(None, 'Mal;')
        and configurar(None, 'x y'))
    ver('sin --lab ni --bd, lo de siempre',
        configurar() is None and BD == BD_POR_DEFECTO and PSQL == psql_antes
        and LAB.endswith('/GitHub/' + LAB_POR_DEFECTO))

    print('--- Escenario tarjeta (D47): análisis sin navegador')
    tok, otro = 'token-de-prueba-1', 'token-de-prueba-2'

    def pet(ruta, t, t_resp, token='', peek=False, **resp):
        reg = peticion_verificacion(
            'http://localhost:8169' + RUTA_VERIF + ruta,
            json.dumps({'jsonrpc': '2.0', 'method': 'call',
                        'params': dict({'peek': peek} if peek else {},
                                       **({'confirm_token': token} if token else {}))}), t)
        reg.update(t_resp=t_resp, terminada=True)
        cuerpo = {'jsonrpc': '2.0', 'result': resp}
        resumen_respuesta(reg, json.dumps(cuerpo), 'WRIT0047')
        return reg

    def bueno(token2=tok, espera=5.55, primero='too_soon', extra=()):
        antes = [pet('pending', 100.0, 100.1, success=True,
                     items=[{'verification_id': 'WRIT0047', 'confirm_token': tok}])]
        despues = [pet('confirm', 101.0, 101.05, tok, success=False, error=primero),
                   pet('pending', 101.1, 101.15, peek=True, success=True, items=[{}])]
        despues += list(extra)
        despues += [pet('confirm', 101.05 + espera, 101.05 + espera + 0.05, token2, success=True,
                        status='confirmed'),
                    pet('execute', 101.2 + espera, 101.6 + espera, tok, success=True,
                        status='executed')]
        return antes + despues, len(antes)

    reg = pet('confirm', 1.0, 1.1, tok, success=False, error='too_soon')
    ver('peticion_verificacion: guarda la huella del token, nunca el token',
        tok not in repr(reg) and reg['huella'] == _huella(tok) and reg['error'] == 'too_soon')
    ver('peticion_verificacion: ignora otras rutas y marca peek',
        peticion_verificacion('http://x/web/dataset/call_kw', '{}', 1) is None
        and pet('pending', 1, 1, peek=True)['peek'])
    ver('resumen_respuesta: un error desconocido queda como «otro» (sin texto)',
        pet('confirm', 1, 1, error='Traceback con datos')['error'] == 'otro')
    registro, n = bueno()
    lineas, incid = analizar_tarjeta(registro, n)
    ver('análisis: too_soon, sin /pending sin peek, 5,55 s, mismo token y ejecutada → sin incidencias',
        not incid and any('con peek 1' in x for x in lineas))
    casos = (
        ('el primer /confirm no es too_soon', bueno(primero='')),
        ('reintento a los 3 s', bueno(espera=3.0)),
        ('token distinto en el segundo /confirm', bueno(token2=otro)),
        ('un /pending sin peek tras el clic', bueno(extra=[pet(
            'pending', 102.0, 102.1, success=True,
            items=[{'verification_id': 'WRIT0047', 'confirm_token': otro}])])),
    )
    for nombre, (registro, n) in casos:
        ver('análisis: %s → incidencia' % nombre, bool(analizar_tarjeta(registro, n)[1]))
    registro, n = bueno()
    ver('análisis: un solo /confirm → incidencia',
        bool(analizar_tarjeta([r for i, r in enumerate(registro) if i != 3], n)[1]))
    ver('análisis: clic a 5 s o más del pintado → incidencia',
        bool(analizar_tarjeta([dict(r, t=r['t'] + 5) if i >= n else r
                               for i, r in enumerate(registro)], n)[1]))
    op = {'id': 9, 'vid': 'WRIT0047', 'status': 'pending', 'executed': False, 'danger': 'high',
          'uid': 12, 'vigente': True, 'restante': 800, 'confirmado_por': 0}
    ver('operación lista: pendiente, high, del uid y sin caducar',
        motivo_tarjeta_no_lista([op], 12) is None)
    ver('operación no lista: caducada, a punto de caducar, de otro uid, dos, ninguna, ya ejecutada',
        all(motivo_tarjeta_no_lista(o, 12) for o in (
            [dict(op, vigente=False)], [dict(op, restante=30)], [dict(op, uid=2)], [op, op], [],
            [dict(op, status='executed', executed=True)])))
    hecha = dict(op, status='executed', executed=True, confirmado_por=12)
    ver('SQL después: ejecutada, confirmada por el uid y comentario escrito → sin incidencias',
        not despues_tarjeta([hecha], 12, 1, True)[1]
        and despues_tarjeta([dict(hecha, status='confirmed', executed=False)], 12, 1, True)[1]
        and despues_tarjeta([hecha], 12, 1, False)[1])
    bd = 'lab_pns_ai_3973_14'
    muestra = '\n'.join((
        'web-1  | 2026-11-17 10:00:01,000 1 ERROR %s odoo.sql_db: bad query: UPDATE ai_safe_operation SET' % bd,
        'web-1  | 2026-11-17 10:00:01,100 1 INFO %s odoo.service.model: SERIALIZATION_FAILURE, retry 1/5 in 0.5 sec...' % bd,
        'web-1  | 2026-11-17 10:00:02,000 1 INFO %s odoo.service.model: SERIALIZATION_FAILURE, retry 2/5 in 1.2 sec...' % bd,
        'web-1  | 2026-11-17 10:00:03,000 1 INFO %s odoo.service.model: SERIALIZATION_FAILURE, maximum number of tries reached' % bd,
        'web-1  | 2026-11-17 10:00:04,000 1 ERROR otra_14 odoo.sql_db: bad query: UPDATE ai_safe_operation SET',
        'web-1  | 2026-11-17 09:00:00,000 1 ERROR %s odoo.sql_db: bad query: UPDATE ai_safe_operation SET' % bd))
    cuenta = contar_tarjeta(muestra, '2026-11-17 09:30:00', bd)
    ver('log de la tarjeta: bad query 1, retry 1/5 1, retry 2/5 1, máximo 1 (BD y marca filtradas)',
        (cuenta['bad_query_aso'], cuenta['retry1'], cuenta['retry_mas'], cuenta['maximo'])
        == (1, 1, 1, 1))


class _Argumentos(argparse.ArgumentParser):
    """argparse sale con 2 por defecto; aquí, con ARGUMENTOS (12)."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(ARGUMENTOS, '%s: error: %s\n' % (self.prog, message))


def _main():
    ap = _Argumentos(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='orden', required=True, parser_class=_Argumentos)
    c = sub.add_parser('c', help='C sobre un log por la entrada estándar')
    r = sub.add_parser('rutas', help='solo las guardas de las rutas')
    r.add_argument('--descarga', action='append', default=[])
    r.add_argument('--pintado', action='store_true')
    r.add_argument('--escenario', choices=['p34', 'tarjeta'])
    r.add_argument('--visible', action='store_true')
    r.add_argument('--espera-turno', type=int, default=ESPERA_TURNO)
    r.add_argument('rutas', nargs='*')
    n = sub.add_parser('navegar', help='entrar y visitar rutas de lab_pns_ai_3973_14')
    n.add_argument('--salida', required=True, help='carpeta para capturas y detalle.txt')
    n.add_argument('--descarga', action='append', default=[],
                   help='ruta de una descarga, para abrirla desde el disco (repetible)')
    n.add_argument('--pintado', action='store_true',
                   help='pintado del aviso del parche 34 por el formatContent real (L1)')
    n.add_argument('--escenario', choices=['p34', 'tarjeta'],
                   help='p34: turnos reales del parche 34 (L2), con pausas y SQL de solo lectura; '
                        'tarjeta: reintento tras too_soon (D47), clic forzado y SQL de solo lectura')
    n.add_argument('--visible', action='store_true', help='Chrome visible (perfil temporal)')
    n.add_argument('--espera-turno', type=int, default=ESPERA_TURNO,
                   help='segundos de espera por turno del escenario (por defecto %d)' % ESPERA_TURNO)
    n.add_argument('rutas', nargs='*', help='rutas que empiezan por /, p. ej. /chatboo/canvas/8')
    s = sub.add_parser('sqlprueba', help='consultas de un escenario contra la BD real (solo lectura)')
    s.add_argument('--escenario', choices=['p34', 'tarjeta'], default='p34')
    for p in (c, r, n, s):
        p.add_argument('--lab', help='carpeta de ~/GitHub del laboratorio (por defecto %s)'
                       % LAB_POR_DEFECTO)
        p.add_argument('--bd', help='BD esperada (por defecto %s)' % BD_POR_DEFECTO)
    a = sub.add_parser('autoprueba', help='prueba contra un servidor simulado')
    a.add_argument('--salida', required=True)
    a.add_argument('--js', help='carpeta static/src/js de pns_ai_chatboo (pintado con los JS reales)')
    args = ap.parse_args()
    # Con la salida en una tubería (tee), cada línea se ve en cuanto se escribe.
    sys.stdout.reconfigure(line_buffering=True)
    if args.orden != 'autoprueba':
        error = configurar(args.lab, args.bd)
        if error:
            print('ABORTADO: %s' % error)
            return ARGUMENTOS
    if args.orden == 'c':
        return resultado_c(io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace'))
    if args.orden == 'rutas':
        if args.espera_turno < 1:
            print('ABORTADO: --espera-turno debe ser 1 o más.')
            return ARGUMENTOS
        return comprobar_rutas(args.rutas + args.descarga)
    if args.orden == 'sqlprueba':
        return sqlprueba_tarjeta() if args.escenario == 'tarjeta' else sqlprueba()
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
