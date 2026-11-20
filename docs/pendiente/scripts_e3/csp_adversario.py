# Comprueba con html5lib el prefijo CSP del parche 27 b (E3′) en 41 diseños adversarios: CSP segundo hijo de <head>, no-quirks.
# Necesita html5lib (pip install html5lib), que no está en la imagen de Odoo: se ejecuta en el equipo,
# desde cualquier carpeta: python3 docs/pendiente/scripts_e3/csp_adversario.py
"""E3′ B1: casos adversarios del prefijo fijo (revisión de odoo-reviewer, 29/10/2026). Solo lee el repo."""
import html as H
import re

import html5lib

import importlib.util
import os
import sys
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
CANVAS = os.path.join(REPO, 'pns_ai_chatboo', 'models', 'chatboo_canvas.py')
TEST = os.path.join(REPO, 'pns_ai_chatboo', 'tests', 'test_seges_chatboo_canvas.py')


def load():
    """Carga chatboo_canvas.py sin Odoo (sustituye ``odoo._``). Solo lee el repo."""
    if 'odoo' not in sys.modules:
        odoo = types.ModuleType('odoo')
        odoo._ = lambda s, *a: (s % a) if a else s
        sys.modules['odoo'] = odoo
    spec = importlib.util.spec_from_file_location('chatboo_canvas_e3p', CANVAS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

c = load()
X = '<script>x()</script><p>t</p>'
CASES = {
 'cierra_head': '</head>' + X, 'cierra_html': '</html>' + X, 'body': '<body>' + X,
 'frameset': '<frameset><frame src="https://e/"></frameset>', 'template': '<template>' + X,
 'noscript': '<noscript>' + X, 'base': '<base href="https://evil/">' + X,
 'plaintext': '<plaintext>' + X, 'xmp': '<xmp>' + X, 'textarea': '<textarea>' + X,
 'title_abierto': '<title>' + X, 'style_abierto': '<style>' + X,
 'script_abierto': '<script>x()', 'texto_suelto': 'hola' + X, 'nul': '\x00' + X,
 'comentario_abierto': '<!--' + X, 'cdata': '<![CDATA[x]]>' + X,
 'svg_cdata': '<svg><![CDATA[</svg>' + X, 'math': '<math>' + X,
 'meta_refresh': '<meta http-equiv="refresh" content="0;url=https://e/">' + X,
 'meta_charset_otro': '<meta charset="windows-1252">' + X,
 'meta_csp_laxa': '<meta http-equiv="Content-Security-Policy" content="default-src *">' + X,
 'doctype_quirks': '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">' + X,
 'doctype_basura': '<!DOCTYPE foo>' + X, 'bom_doctype': '﻿<!doctype html>' + X,
 'xml_pi': '<?xml version="1.0"?>' + X, 'cierra_script': '</script>' + X,
 'comillas': '"><script>y()</script>&quot;' + X, 'table': '<table>' + X,
 'select': '<select>' + X, 'iframe': '<iframe>' + X, 'object': '<object>' + X,
 'html_manifest': '<html manifest="https://e/m">' + X, 'head_attrs': '<head profile=x>' + X,
 'solo_script': '<script>a()</script>', 'body_end_en_script': '<script>"</body>"</script>' + X,
 'noche': '<style>[data-theme=dark]{}</style>' + X,
 'cr_lf': '\r\n\r\n' + X, 'ff': '\f' + X, 'lt_solo': '<' + X, 'etiqueta_rota': '<a' + X,
}


def check(doc):
    p = html5lib.HTMLParser(tree=html5lib.getTreeBuilder('etree'), namespaceHTMLElements=False)
    root = p.parse(doc)
    head = root.find('head')
    kids = list(head)
    ok_head = (len(kids) >= 2 and kids[0].tag == 'meta' and kids[0].get('charset') == 'utf-8'
               and kids[1].get('http-equiv') == 'Content-Security-Policy'
               and kids[1].get('content', '').startswith("default-src 'none'"))
    first = [e.tag for e in root.iter()][:4]  # html, head, meta, meta
    return ok_head and first == ['html', 'head', 'meta', 'meta'], p.compatMode


bad = 0
for name, d in CASES.items():
    dl = c.downloadable_page(d)
    page = c.canvas_page(d)
    m = re.search(r'srcdoc="([^"]*)"', page)
    src = H.unescape(m.group(1))
    a, ma = check(dl)
    b, mb = check(src)
    pref = dl.startswith(c._CSP_PREFIX) and src.startswith(c._CSP_PREFIX)
    # el diseño va tal cual tras el prefijo (salvo inyecciones posteriores en el cuerpo)
    raw = dl[len(c._CSP_PREFIX):].startswith(d[:5]) and src[len(c._CSP_PREFIX):].startswith(d[:5])
    ok = a and b and ma == mb == 'no quirks' and pref and raw
    bad += not ok
    print('%-20s %s descarga=%s srcdoc=%s' % (name, 'OK ' if ok else 'MAL', ma, mb))
print('casos: %d · MAL: %d' % (len(CASES), bad))
# el escape del atributo es posterior: el srcdoc crudo no tiene comillas sin escapar
print('srcdoc sin comillas crudas:', all('"' not in re.search(r'srcdoc="([^"]*)"', c.canvas_page(d)).group(1)
                                         for d in CASES.values()))
print('vacío/espacios ->', repr(c.downloadable_page('  ')), repr(re.search(r'srcdoc="([^"]*)"', c.canvas_page('  ')).group(1)))
