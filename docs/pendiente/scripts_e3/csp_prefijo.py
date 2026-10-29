# Comprueba con html5lib el prefijo CSP del parche 27 b (E3′) en 37 diseños: los 23 de la revisión y B1_DESIGNS del test.
# Necesita html5lib (pip install html5lib), que no está en la imagen de Odoo: se ejecuta en el equipo,
# desde cualquier carpeta: python3 docs/pendiente/scripts_e3/csp_prefijo.py
"""B1 tras la decisión de Sergio (29/10/2026): _with_csp antepone un prefijo fijo.

En la descarga y en el srcdoc desescapado: meta charset y CSP son los dos primeros hijos de
<head>, ningún script va antes de la CSP, lo servido empieza por el prefijo y el modo es no-quirks.
"""
import ast
import html as htmlmod
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

# Los 23 casos de la primera revisión (antes en csp_html5.py).
CASES = {
    'doctype': '<!DOCTYPE html><html><head><title>t</title></head><body><script>1</script></body></html>',
    'sin_doctype_sin_head': '<html><body><script>1</script></body></html>',
    'solo_body': '<body><p>x</p></body>',
    'html_head_attrs': '<!doctype html><html lang="es" class="x"><head data-a="1"><meta charset="utf-8"></head><body></body></html>',
    'mayusculas': '<!DOCTYPE HTML><HTML><HEAD><TITLE>t</TITLE></HEAD><BODY><SCRIPT>1</SCRIPT></BODY></HTML>',
    'espacios_iniciales': '  \n\t<!DOCTYPE html><html><head></head><body></body></html>',
    'bom': '﻿<!DOCTYPE html><html><head></head><body><script>1</script></body></html>',
    'script_antes_head': '<!DOCTYPE html><html><script>1</script><head><title>t</title></head><body></body></html>',
    'head_en_comentario': '<!DOCTYPE html><!-- <head> --><html><script>1</script><head></head><body></body></html>',
    'head_en_cadena_script': '<!DOCTYPE html><script>var s="<head>";</script><head></head><body></body>',
    'meta_csp_propia': '<!DOCTYPE html><html><head><meta http-equiv="Content-Security-Policy" content="default-src *"></head><body></body></html>',
    'comentario_antes_doctype': '<!-- c --><!DOCTYPE html><html><head></head><body></body></html>',
    # Casos adversos (diseño controlado por la inyección):
    'comentario_abrupto_<!-->': '<!DOCTYPE html><!--><script>EVIL</script>--><html><head></head><body></body></html>',
    'comentario_<!--->': '<!DOCTYPE html><!---><script>EVIL</script>--><head></head><body></body>',
    'comentario_--!>': '<!DOCTYPE html><!-- x --!><script>EVIL</script>--><head></head><body></body>',
    'nbsp_inicial': '\xa0<!DOCTYPE html><html><head></head><body><script>EVIL</script></body></html>',
    'nbsp_tras_doctype': '<!DOCTYPE html>\xa0<head></head><body><script>EVIL</script></body>',
    'vt_inicial': '\x0b<head></head><body><script>EVIL</script></body>',
    'html-custom': '<!DOCTYPE html><html-x><script>EVIL</script>',
    'head-custom': '<!DOCTYPE html><head-x><script>EVIL</script>',
    'html_attr_con_>': '<!DOCTYPE html><html data-x=">"><script>EVIL</script><head></head><body></body></html>',
    'head_attr_con_>': '<!DOCTYPE html><html><head data-x=">"><script>EVIL</script></head><body></body></html>',
    'xml_decl': '<?xml version="1.0"?><!DOCTYPE html><html><head></head><body></body></html>',
}

tree = ast.parse(open(TEST, encoding='utf-8').read())
b1 = next(n.value for n in tree.body if isinstance(n, ast.Assign)
          and getattr(n.targets[0], 'id', '') == 'B1_DESIGNS')
cases = dict(CASES)
for i, node in enumerate(b1.elts):
    cases['test_B1_%02d' % i] = ast.literal_eval(node)


def check(doc):
    p = html5lib.HTMLParser(tree=html5lib.getTreeBuilder('etree'), namespaceHTMLElements=False)
    root = p.parse(doc)
    head = root.find('head')
    kids = list(head) if head is not None else []
    ours = (len(kids) >= 2 and kids[0].tag == 'meta' and kids[0].get('charset') == 'utf-8'
            and kids[1].tag == 'meta'
            and (kids[1].get('content') or '').startswith("default-src 'none'"))
    order = [e for e in root.iter() if e.tag in ('script', 'meta')]
    idx = next(i for i, e in enumerate(order) if e is kids[1]) if ours else None
    before = ours and any(e.tag == 'script' for e in order[:idx])
    return ours, before, p.compatMode


bad = 0
print('\n######## PREFIJO FIJO ########')
for name, design in cases.items():
    dl = c.downloadable_page(design)
    src = htmlmod.unescape(re.search(r'srcdoc="([^"]*)"', c.canvas_page(design)).group(1))
    res = []
    for doc in (dl, src):
        ours, before, mode = check(doc)
        res.append(ours and not before and mode == 'no quirks'
                   and doc.startswith(c._CSP_PREFIX))
        res.append(mode)
    ok = res[0] and res[2]
    bad += not ok
    print('%-26s %s descarga=%s srcdoc=%s' % (name, 'OK ' if ok else 'MAL', res[1], res[3]))
print('casos: %d · MAL: %d' % (len(cases), bad))
