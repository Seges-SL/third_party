"""Compara el core del paquete de la imagen con la referencia (solo lectura).

Uso: python3 -I /src/comparar_core.py resumen
     python3 -I /src/comparar_core.py hunks <clave> [<clave> ...]
     python3 -I /src/comparar_core.py diff <clave>
Clave = ruta relativa a /usr/lib/python3/dist-packages (p. ej. odoo/fields.py).
"""
import ast
import collections
import difflib
import hashlib
import os
import re
import sys

IMG = "/usr/lib/python3/dist-packages"
REF = "/ref"
EXCL_SEG = {"__pycache__", "i18n", "i18n_extra"}
EXCL_PARES = [("static", "lib"), ("static", "img"), ("static", "description"),
              ("static", "fonts")]
HUELLAS = ["odoo/fields.py", "odoo/models.py",
           "odoo/addons/auth_totp/models/res_users.py",
           "odoo/addons/auth_signup/models/res_partner.py",
           "odoo/addons/iap/models/iap_account.py"]


def excluida(clave):
    seg = clave.split("/")
    if EXCL_SEG.intersection(seg[:-1]) or clave.endswith(".pyc"):
        return True
    for i in range(len(seg) - 2):
        if (seg[i], seg[i + 1]) in EXCL_PARES:
            return True
        if seg[i:i + 3] == ["static", "src", "img"]:
            return True
    return False


def recorrer(raiz, prefijo, saltar=None):
    out = {}
    for d, dirs, files in os.walk(raiz):
        if saltar and os.path.abspath(d) == saltar:
            dirs[:] = []
            continue
        for f in files:
            abs_ = os.path.join(d, f)
            clave = prefijo + os.path.relpath(abs_, raiz)
            out[clave] = abs_
    return out


def imagen():
    return recorrer(IMG + "/odoo", "odoo/")


def referencia():
    out = recorrer(REF + "/odoo", "odoo/")
    for k, v in recorrer(REF + "/addons", "odoo/addons/").items():
        if k in out:
            print("COLISION", k)
        out[k] = v
    return out


def contenido(p):
    if os.path.islink(p):
        return ("LINK:" + os.readlink(p)).encode()
    with open(p, "rb") as fh:
        return fh.read()


def h16(p):
    return hashlib.sha256(contenido(p)).hexdigest()[:16]


def modulo(clave):
    s = clave.split("/")
    if len(s) > 3 and s[1] == "addons":
        return "odoo/addons/" + s[2]
    return "/".join(s[:2])


def resumen():
    im = {k: v for k, v in imagen().items() if not excluida(k)}
    rf = {k: v for k, v in referencia().items() if not excluida(k)}
    comunes = sorted(set(im) & set(rf))
    dist = [k for k in comunes if contenido(im[k]) != contenido(rf[k])]
    solo_i = sorted(set(im) - set(rf))
    solo_r = sorted(set(rf) - set(im))
    print("RECUENTO iguales=%d distintos=%d solo_imagen=%d solo_referencia=%d"
          % (len(comunes) - len(dist), len(dist), len(solo_i), len(solo_r)))
    print("== DISTINTOS")
    for k in dist:
        print("D", k)
    for nombre, lista in (("SOLO_IMAGEN", solo_i), ("SOLO_REFERENCIA", solo_r)):
        print("==", nombre, "(por módulo o carpeta)")
        for m, n in sorted(collections.Counter(modulo(k) for k in lista).items()):
            print("  %-55s %d" % (m, n))
        print("== %s (rutas)" % nombre)
        for k in lista:
            print(nombre[5], k)
    print("== HUELLAS (imagen | referencia)")
    for k in HUELLAS:
        a = h16(im[k]) if k in im else "-"
        b = h16(rf[k]) if k in rf else "-"
        print("  %-48s %s | %s" % (k, a, b))
    requisitos()


def requisitos():
    print("== REQUISITOS")
    eggs = [e for e in os.listdir(IMG) if e.startswith("odoo-") and "info" in e]
    for e in eggs:
        rq = os.path.join(IMG, e, "requires.txt")
        print("  imagen", e, "requires.txt:", os.path.exists(rq))
    eg_req = []
    if eggs and os.path.exists(os.path.join(IMG, eggs[0], "requires.txt")):
        eg_req = [l.strip() for l in open(os.path.join(IMG, eggs[0], "requires.txt"))
                  if l.strip() and not l.startswith("[")]
    ref_req = []
    tree = ast.parse(open(REF + "/setup.py").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.keyword) and n.arg == "install_requires":
            ref_req = [ast.literal_eval(e) for e in n.value.elts]
    print("  setup.py install_requires: solo_ref=%s solo_egg=%s"
          % (sorted(set(ref_req) - set(eg_req)), sorted(set(eg_req) - set(ref_req))))
    # requirements.txt de la referencia, evaluado para el Python de la imagen
    try:
        import pkg_resources
    except ImportError:
        print("  sin pkg_resources")
        return
    for linea in open(REF + "/requirements.txt"):
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        try:
            req = pkg_resources.Requirement.parse(linea)
        except Exception as exc:  # noqa
            print("  NO_PARSE", linea, exc)
            continue
        if req.marker and not req.marker.evaluate():
            continue
        try:
            inst = pkg_resources.get_distribution(req.project_name).version
        except pkg_resources.DistributionNotFound:
            inst = "NO_INSTALADO"
        ok = inst in req if inst != "NO_INSTALADO" else False
        print("  %-3s %-45s instalado=%s" % ("OK" if ok else "DIF", str(req).split(";")[0], inst))


def def_contexto(lineas, idx):
    for i in range(min(idx, len(lineas) - 1), -1, -1):
        m = re.match(r"\s*(def|class)\s+(\w+)", lineas[i])
        if m:
            return lineas[i].strip().split("(")[0].rstrip(":")
    return "-"


def hunks(claves):
    im, rf = imagen(), referencia()
    for k in claves:
        if k not in im or k not in rf:
            print("##", k, "falta en", "imagen" if k not in im else "referencia")
            continue
        a = contenido(im[k]).decode("utf-8", "replace").splitlines()
        b = contenido(rf[k]).decode("utf-8", "replace").splitlines()
        if a == b:
            print("##", k, "IGUAL")
            continue
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
        print("## %s: %d bloques (imagen -> referencia)" % (k, len(ops)))
        for tag, i1, i2, j1, j2 in ops:
            print("   %s img:%d-%d ref:%d-%d  -%d +%d  en %s | ref %s"
                  % (tag, i1 + 1, i2, j1 + 1, j2, i2 - i1, j2 - j1,
                     def_contexto(a, i1), def_contexto(b, j1)))


def diff(k):
    im, rf = imagen(), referencia()
    a = contenido(im[k]).decode("utf-8", "replace").splitlines()
    b = contenido(rf[k]).decode("utf-8", "replace").splitlines()
    for l in difflib.unified_diff(a, b, "imagen/" + k, "ref/" + k, lineterm="", n=2):
        print(l)


if __name__ == "__main__":
    modo = sys.argv[1]
    if modo == "resumen":
        resumen()
    elif modo == "hunks":
        hunks(sys.argv[2:])
    elif modo == "diff":
        diff(sys.argv[2])
